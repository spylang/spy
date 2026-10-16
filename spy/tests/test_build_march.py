"""
Tests for `spy build --march` and for the per-march libspy build.

They are organized from the cheapest to the most expensive:

  1. pure functions in spy.build.flags (no subprocess, no compiler)
  2. consistency between spy.build.flags and libspy/Makefile (`make -n`)
  3. CompilerConfig wiring, with the `make` step stubbed out
  4. CompilerConfig._ensure_libspy_built, with subprocess.run faked
  5. CLI validation (no compilation)
  6. real end-to-end builds (they compile libspy and a tiny program, ~1s each)

We always pass `--gc none` in the end-to-end tests so that they don't depend
on libgc being installed: --march has nothing to do with the GC.
"""

import platform
import re
import shutil
import subprocess
import sys
import textwrap
from typing import Any, Optional

import py.path
import pytest
from typer.testing import CliRunner

import spy.libspy
from spy.build.config import BuildConfig, CompilerConfig
from spy.build.flags import (
    check_march,
    get_build_dirname,
    get_cflags,
    get_libdir,
    validate_march,
)
from spy.build.flags import main as flags_main
from spy.cli import app
from spy.errors import SPyError

IS_DARWIN = sys.platform == "darwin"


def host_march() -> Optional[str]:
    """
    A -march value which is valid for both gcc and clang on this host, and
    which is NOT the special value "native".
    """
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "x86-64-v2"
    if machine in ("arm64", "aarch64"):
        return "armv8-a"
    return None


IS_X86 = platform.machine().lower() in ("x86_64", "amd64")

VALID_MARCHES = ["native", "x86-64-v3", "x86_64_v3", "armv8.2-a+crc", "znver4"]

# anything which is not [A-Za-z0-9._+-], or which does not start with an
# alphanumeric char: these end up in a shell command line and in a dirname
INVALID_MARCHES = [
    "",
    " ",
    "a b",
    "a/b",
    "../x",
    "-native",
    "a;b",
    "$(x)",
    "a'b",
    'a"b',
    "a\nb",
    "caf\u00e9",
]


def march_flags(flags: list[str]) -> list[str]:
    return [f for f in flags if f.startswith("-march")]


def flat(output: str) -> str:
    """
    Make a CLI error message easy to grep: typer draws errors in a box and wraps
    long lines, so drop the box and collapse whitespace.
    """
    output = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", output)
    output = re.sub(r"[│╭╮╰╯─]", " ", output)
    return " ".join(output.split())


# ======================================================================
# 1. spy.build.flags: pure functions
# ======================================================================


class TestFlags:
    def test_cflags_with_march(self):
        cflags = get_cflags("native", "release", march="x86-64-v3")
        assert march_flags(cflags) == ["-march=x86-64-v3"]
        # -march must come together with -flto: this is the whole point of
        # having a libspy per march
        assert "-flto" in cflags

    @pytest.mark.parametrize(
        "target", ["native", "native-static", "wasi", "emscripten"]
    )
    @pytest.mark.parametrize("build_type", ["debug", "release"])
    def test_cflags_without_march(self, target, build_type):
        assert march_flags(get_cflags(target, build_type)) == []

    @pytest.mark.parametrize(
        "build_type, kind, march, expected",
        [
            ("release", "exe", None, "release"),
            ("debug", "exe", None, "debug"),
            ("debug", "testlib", None, "debug-testlib"),
            ("release", "exe", "native", "release-march-native"),
            ("debug", "exe", "x86-64-v3", "debug-march-x86-64-v3"),
            ("debug", "testlib", "native", "debug-testlib-march-native"),
        ],
    )
    def test_build_dirname(self, build_type, kind, march, expected):
        assert get_build_dirname(build_type, kind, march) == expected

    @pytest.mark.parametrize("march", VALID_MARCHES)
    def test_validate_march_accepts(self, march):
        assert validate_march(march) == march

    @pytest.mark.parametrize("march", INVALID_MARCHES)
    def test_validate_march_rejects(self, march):
        with pytest.raises(ValueError, match="invalid --march value"):
            validate_march(march)

    @pytest.mark.parametrize("march", INVALID_MARCHES)
    def test_invalid_march_is_rejected_everywhere(self, march):
        # we never try to "sanitize" a value: the dirname computed here must be
        # the one computed by the Makefile, and the cflags must not be able to
        # smuggle anything
        with pytest.raises(ValueError, match="invalid --march value"):
            get_cflags("native", "release", march=march)
        with pytest.raises(ValueError, match="invalid --march value"):
            get_build_dirname("release", "exe", march)
        with pytest.raises(ValueError, match="invalid --march value"):
            get_libdir("native", "release", "exe", march)

    def test_flags_cli_rejects_invalid_march(self, capsys):
        with pytest.raises(SystemExit) as exc:
            flags_main(["--cflags", "--target=native", "--march=a b"])
        assert exc.value.code == 2
        assert "invalid --march value" in capsys.readouterr().err

    def test_different_march_different_libdir(self):
        d_none = get_libdir("native", "release")
        d_native = get_libdir("native", "release", march="native")
        d_v3 = get_libdir("native", "release", march="x86-64-v3")
        assert len({d_none, d_native, d_v3}) == 3
        # a march-less libdir is the historical one
        assert d_none.endswith("/native/release")

    def test_flags_cli(self, capsys):
        # this is the interface used by libspy/Makefile
        flags_main(["--cflags", "--target=native", "--march=native"])
        assert "-march=native" in capsys.readouterr().out

        flags_main(
            ["--libdir", "--target=native", "--build-type=release", "--march=native"]
        )
        assert capsys.readouterr().out.strip().endswith("release-march-native")


# ======================================================================
# 2. spy.build.flags <-> libspy/Makefile
# ======================================================================


class TestPythonMakefileConsistency:
    """
    The build dir name is computed twice: by get_build_dirname() in Python and
    by libspy/Makefile. If they disagree, Python looks for libspy.a where make
    never put it. Ask make where it is going to put things.
    """

    @pytest.mark.parametrize("march", [None, "native", "x86-64-v3", "armv8.2-a+crc"])
    def test_make_builddir_matches_get_libdir(self, march):
        cmd = [
            "make", "-n", "-B",  # -n: dry-run, -B: pretend everything is stale
            "-C", str(spy.libspy.BUILD.dirpath()),
            "TARGET=native",
            "BUILD_TYPE=release",
            "OUTPUT_KIND=exe",
        ]  # fmt: skip
        if march is not None:
            cmd.append(f"MARCH={march}")
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        expected = get_libdir("native", "release", "exe", march)
        # make prints paths relative to libspy/: e.g. build/native/release/libspy.a
        rel = py.path.local(expected).relto(spy.libspy.BUILD.dirpath())
        assert f"{rel}/libspy.a" in out


class TestMakefileMarch:
    @staticmethod
    def make(*assignments: str) -> "subprocess.CompletedProcess[str]":
        cmd = [
            "make", "-n",
            "-C", str(spy.libspy.BUILD.dirpath()),
            "TARGET=native", "BUILD_TYPE=debug", "OUTPUT_KIND=exe",
            *assignments,
        ]  # fmt: skip
        return subprocess.run(cmd, capture_output=True, text=True)

    @pytest.mark.parametrize(
        "march",
        [
            "x; touch {marker}",
            "x `touch {marker}`",
            "x $(touch {marker})",
            "x' ; touch {marker} ; '",
            'x" ; touch {marker} ; "',
        ],
    )
    def test_march_is_not_evaluated(self, tmpdir, march):
        marker = tmpdir.join("pwned")
        self.make("MARCH=" + march.format(marker=marker))
        assert not marker.check()

    def test_valid_march(self):
        res = self.make("MARCH=x86-64-v3")
        assert res.returncode == 0, res.stderr
        assert "-march=x86-64-v3" in res.stdout

    def test_no_march(self):
        res = self.make()
        assert res.returncode == 0, res.stderr
        assert "-march" not in res.stdout


class TestCheckMarch:
    """
    check_march() asks the real C compiler whether it accepts the value, so
    that we can fail early, with a clear message, instead of dumping the
    compiler output (zig prints the list of ALL the CPUs it knows).
    """

    @pytest.mark.skipif(IS_DARWIN, reason="-march=native varies with Apple clang")
    def test_native(self):
        check_march("native", "native")

    @pytest.mark.skipif(host_march() is None, reason="unknown architecture")
    def test_host_march(self):
        check_march("native", host_march())  # type: ignore[arg-type]

    def test_syntax_is_checked_first(self):
        with pytest.raises(ValueError, match="invalid --march value"):
            check_march("native", "a b")

    def test_unknown_march(self):
        with pytest.raises(ValueError) as exc:
            check_march("native", "not-a-real-arch")
        msg = str(exc.value)
        assert "'not-a-real-arch' is not a valid -march value" in msg
        # this is a gcc/clang problem, don't confuse the user with zig
        assert "zig" not in msg
        # a concise message, not a dump of the compiler output
        assert len(msg.splitlines()) <= 3

    @pytest.mark.skipif(IS_DARWIN, reason="--static is not supported on macOS")
    def test_static_native(self):
        check_march("native-static", "native")

    @pytest.mark.skipif(IS_DARWIN or not IS_X86, reason="x86 and zig only")
    def test_static_zig_cpu_names(self):
        # zig has its own CPU names: these are fine for zig...
        check_march("native-static", "x86_64_v3")
        check_march("native-static", "haswell")
        # ... but the gcc spelling is not, and the message says what to do
        with pytest.raises(ValueError) as exc:
            check_march("native-static", "x86-64-v3")
        msg = str(exc.value)
        assert "'x86-64-v3' is not a valid -march value" in msg
        assert "zig" in msg
        assert "x86_64_v3" in msg
        assert "python -m ziglang targets" in msg
        # zig lists hundreds of CPUs: we must not dump them
        assert len(msg.splitlines()) <= 4


# ======================================================================
# 3. CompilerConfig wiring (the make step is stubbed out)
# ======================================================================


@pytest.fixture
def ensure_calls(monkeypatch):
    """
    Replace CompilerConfig._ensure_libspy_built with a recorder, so that we can
    inspect the flags without ever invoking make.
    """
    calls: list[tuple] = []

    def fake(*args):
        calls.append(args)

    monkeypatch.setattr(CompilerConfig, "_ensure_libspy_built", staticmethod(fake))
    return calls


class TestCompilerConfig:
    def test_march_in_cflags_and_libdir(self, ensure_calls):
        cfg = BuildConfig(
            target="native",
            kind="exe",
            build_type="release",
            gc="none",
            march="x86-64-v3",
        )
        comp = CompilerConfig(cfg)
        assert march_flags(comp.cflags) == ["-march=x86-64-v3"]
        # we link against the libspy built for this march, not the default one
        libdir = comp.ldflags[comp.ldflags.index("-L") + 1]
        assert libdir == get_libdir("native", "release", "exe", "x86-64-v3")
        assert ensure_calls == [("native", "release", "exe", "x86-64-v3")]

    def test_no_march(self, ensure_calls):
        cfg = BuildConfig(target="native", kind="exe", build_type="release", gc="none")
        comp = CompilerConfig(cfg)
        assert march_flags(comp.cflags) == []
        libdir = comp.ldflags[comp.ldflags.index("-L") + 1]
        assert libdir == get_libdir("native", "release", "exe")

    @pytest.mark.skipif(IS_DARWIN, reason="--static is not supported on macOS")
    def test_static(self, ensure_calls):
        cfg = BuildConfig(
            target="native",
            kind="exe",
            build_type="release",
            gc="none",
            static=True,
            march="native",
        )
        comp = CompilerConfig(cfg)
        assert march_flags(comp.cflags) == ["-march=native"]
        libdir = comp.ldflags[comp.ldflags.index("-L") + 1]
        assert libdir == get_libdir("native-static", "release", "exe", "native")
        assert ensure_calls == [("native-static", "release", "exe", "native")]

    @pytest.mark.parametrize("target", ["wasi", "emscripten"])
    def test_march_with_wasm_is_rejected(self, ensure_calls, target):
        # the CLI already checks this; this is the last-resort check for
        # callers which build a BuildConfig by hand
        cfg = BuildConfig(
            target=target, kind="exe", build_type="release", gc="none", march="native"
        )
        with pytest.raises(AssertionError, match="--march is only supported"):
            CompilerConfig(cfg)


# ======================================================================
# 4. CompilerConfig._ensure_libspy_built
# ======================================================================


class FakeMake:
    """
    Fake subprocess.run: records the make invocations and, like the real make,
    leaves a libspy.a in the libdir.
    """

    def __init__(self, libdir: py.path.local, *, creates_libspy_a: bool = True):
        self.libdir = libdir
        self.creates_libspy_a = creates_libspy_a
        self.cmdlines: list[list[str]] = []

    def __call__(self, cmdline: list[str], **kwargs: Any) -> None:
        assert kwargs.get("check") is True
        self.cmdlines.append(cmdline)
        if self.creates_libspy_a:
            self.libdir.ensure("libspy.a")


@pytest.fixture
def fake_make(monkeypatch, tmpdir):
    libdir = py.path.local(tmpdir).join("libdir")
    monkeypatch.setattr("spy.build.config.get_libdir", lambda *args: str(libdir))
    fake = FakeMake(libdir)
    monkeypatch.setattr(subprocess, "run", fake)
    return fake


class TestEnsureLibspyBuilt:
    def test_no_march_does_nothing(self, fake_make):
        # without --march we keep using the libspy built by `make -C spy/libspy`
        CompilerConfig._ensure_libspy_built("native", "release", "exe", None)
        assert fake_make.cmdlines == []

    def test_make_args(self, fake_make):
        CompilerConfig._ensure_libspy_built("native", "release", "exe", "x86-64-v3")
        assert len(fake_make.cmdlines) == 1
        cmdline = fake_make.cmdlines[0]
        assert cmdline[0] == "make"
        assert str(spy.libspy.BUILD.dirpath()) in cmdline
        for arg in [
            "TARGET=native",
            "BUILD_TYPE=release",
            "OUTPUT_KIND=exe",
            "MARCH=x86-64-v3",
        ]:
            assert arg in cmdline

    def test_static_target_is_forwarded(self, fake_make):
        CompilerConfig._ensure_libspy_built("native-static", "debug", "exe", "native")
        assert "TARGET=native-static" in fake_make.cmdlines[0]

    def test_rebuild_if_libspy_a_already_exists(self, fake_make):
        """
        libspy.a already being there does NOT mean that it is up to date: the
        libspy sources (or headers) might have changed since.  The only one who
        knows is make, which is a no-op when everything is up to date.

        Regression test: we used to return early if libspy.a existed, and
        silently link against a stale libspy.a.
        """
        fake_make.libdir.ensure("libspy.a")
        CompilerConfig._ensure_libspy_built("native", "release", "exe", "native")
        assert len(fake_make.cmdlines) == 1

    @pytest.mark.parametrize("march", INVALID_MARCHES)
    def test_invalid_march_never_reaches_make(self, monkeypatch, march):
        # libspy/Makefile doesn't validate MARCH: this is the guard
        def no_make(*args, **kwargs):
            raise AssertionError("make must not be called with an invalid march")

        monkeypatch.setattr(subprocess, "run", no_make)
        with pytest.raises(ValueError, match="invalid --march value"):
            CompilerConfig._ensure_libspy_built("native", "release", "exe", march)

    def test_make_does_not_produce_libspy_a(self, monkeypatch, fake_make):
        fake_make.creates_libspy_a = False
        with pytest.raises(SPyError, match="expected .*libspy.a to exist") as exc:
            CompilerConfig._ensure_libspy_built("native", "release", "exe", "native")
        assert exc.value.etype == "W_WIP"

    def test_make_failure_propagates(self, monkeypatch, tmpdir):
        monkeypatch.setattr(
            "spy.build.config.get_libdir", lambda *args: str(tmpdir.join("libdir"))
        )

        def failing_make(cmdline, **kwargs):
            raise subprocess.CalledProcessError(2, cmdline)

        monkeypatch.setattr(subprocess, "run", failing_make)
        with pytest.raises(subprocess.CalledProcessError):
            CompilerConfig._ensure_libspy_built("native", "release", "exe", "native")


# ======================================================================
# 5. CLI validation
# ======================================================================


@pytest.fixture
def main_spy(tmpdir):
    f = tmpdir.join("main.spy")
    f.write(
        textwrap.dedent("""
        def main() -> None:
            print("hello world")
        """)
    )
    return f


def invoke_build(tmpdir, main_spy, *args: str):
    runner = CliRunner()
    cmdline = ["build", "--build-dir", str(tmpdir), *args, str(main_spy)]
    print("spy", " ".join(cmdline))
    res = runner.invoke(app, cmdline)
    print(res.output)
    return res


class TestCli:
    @pytest.mark.parametrize("target", ["wasi", "emscripten"])
    def test_march_requires_native_target(self, tmpdir, main_spy, target):
        res = invoke_build(tmpdir, main_spy, "--target", target, "--march", "native")
        assert res.exit_code == 2  # click.UsageError
        assert "--march can only be used with --target native" in flat(res.output)

    @pytest.mark.parametrize("march", ["a b", "a;b", "-x", "$(x)"])
    def test_march_syntax(self, tmpdir, main_spy, march):
        res = invoke_build(tmpdir, main_spy, "--march", march)
        assert res.exit_code == 2
        assert "invalid --march value" in flat(res.output)
        # we fail before generating anything
        assert not tmpdir.join("build.ninja").check()

    def test_march_unknown_to_the_compiler(self, tmpdir, main_spy):
        res = invoke_build(tmpdir, main_spy, "--march", "not-a-real-arch")
        assert res.exit_code == 2
        assert "'not-a-real-arch' is not a valid -march value" in flat(res.output)
        assert not tmpdir.join("build.ninja").check()

    @pytest.mark.skipif(IS_DARWIN or not IS_X86, reason="x86 and zig only")
    def test_static_march_with_gcc_spelling(self, tmpdir, main_spy):
        res = invoke_build(tmpdir, main_spy, "--static", "--march", "x86-64-v3")
        assert res.exit_code == 2
        out = flat(res.output)
        assert "'x86-64-v3' is not a valid -march value" in out
        assert "x86_64_v3" in out
        assert not tmpdir.join("build.ninja").check()

    def test_march_in_help(self):
        res = CliRunner().invoke(app, ["build", "--help"])
        assert "--march" in flat(res.output)


# ======================================================================
# 6. real end-to-end builds
# ======================================================================

MARCHES = [
    pytest.param(
        "native",
        marks=pytest.mark.skipif(
            IS_DARWIN, reason="-march=native is not reliably supported by Apple clang"
        ),
        id="native",
    ),
    pytest.param(
        host_march(),
        marks=pytest.mark.skipif(host_march() is None, reason="unknown architecture"),
        id="host_march",
    ),
]


class TestEndToEnd:
    @pytest.mark.parametrize("march", MARCHES)
    def test_build_and_run(self, tmpdir, main_spy, capfd, march):
        """
        Build a program with --march. In release mode this exercises the
        -flto + -march combination which motivated having a libspy per march.
        """
        args = ["--gc", "none", "--march", march, "-x", "--release"]
        res = invoke_build(tmpdir, main_spy, *args)
        assert res.exit_code == 0, res.exception
        out, err = capfd.readouterr()
        assert "hello world" in out

        # the libspy built for this march is the one which has been used...
        libdir = py.path.local(get_libdir("native", "release", "exe", march))
        assert libdir.join("libspy.a").check(file=True)
        # ... and the executable actually links to it
        ninja = tmpdir.join("build.ninja").read()
        assert f"-march={march}" in ninja
        assert f"-L {libdir}" in ninja

    @pytest.mark.skipif(IS_DARWIN, reason="--static is not supported on macOS")
    def test_build_static(self, tmpdir, main_spy, capfd):
        # --static goes through `zig cc`, which does not understand the same
        # -march values as gcc (e.g. 'x86-64-v3' is rejected). 'native' works
        # on both.
        res = invoke_build(
            tmpdir, main_spy, "--gc", "none", "--static", "--march", "native", "-x"
        )
        assert res.exit_code == 0, res.exception
        out, err = capfd.readouterr()
        assert "hello world" in out
        libdir = py.path.local(get_libdir("native-static", "debug", "exe", "native"))
        assert libdir.join("libspy.a").check(file=True)

    def test_without_march_is_unchanged(self, tmpdir, main_spy):
        # no -march in the generated build.ninja: the default build is
        # unaffected by the existence of --march
        res = invoke_build(tmpdir, main_spy, "--gc", "none", "--no-compile")
        assert res.exit_code == 0, res.exception
        ninja = tmpdir.join("build.ninja").read()
        assert "-march" not in ninja
        assert "-march-" not in ninja

    def test_invalid_march_is_not_silently_ignored(self, tmpdir, main_spy):
        # a bogus value must make the build fail early, and it must not leave
        # anything behind in libspy/build
        bogus = "not-a-real-arch"
        libdir = py.path.local(get_libdir("native", "debug", "exe", bogus))
        # don't depend on (or leak) leftovers of other runs
        shutil.rmtree(libdir, ignore_errors=True)
        try:
            res = invoke_build(tmpdir, main_spy, "--gc", "none", "--march", bogus)
            assert res.exit_code == 2
            assert not libdir.check()
        finally:
            shutil.rmtree(libdir, ignore_errors=True)
