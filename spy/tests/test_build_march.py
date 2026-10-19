"""
Tests for `spy build --march`.

They are organized from the cheapest to the most expensive:

  1. pure functions in spy.build.flags (no subprocess, no compiler)
  2. CompilerConfig wiring, with the libspy build stubbed out
  3. CLI validation (no compilation)
  4. real end-to-end builds (they compile libspy and a tiny program, ~1s each)

We always pass `--gc none` in the end-to-end tests so that they don't depend
on libgc being installed: --march has nothing to do with the GC.
"""

import platform
import re
import sys
import textwrap
from typing import Optional

import py.path
import pytest
from typer.testing import CliRunner

from spy.build.config import BuildConfig, CompilerConfig
from spy.build.flags import (
    check_march,
    get_build_dirname,
    get_cflags,
    get_libdir,
    validate_march,
)
from spy.cli import app
from spy.libspy import builder as libspy_builder
from spy.libspy.builder import ensure_libspy

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


@pytest.fixture(autouse=True, scope="module")
def private_cache(tmp_path_factory):
    """
    The libspy variants built by these tests go to a private cache, not to the
    one of the user. It is shared by all the tests of the module, so that each
    variant is compiled only once.
    """
    mp = pytest.MonkeyPatch()
    mp.setenv("SPY_CACHE_DIR", str(tmp_path_factory.mktemp("spy-cache")))
    yield
    mp.undo()


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
        "build_type, kind, expected",
        [
            ("release", "exe", "release"),
            ("debug", "exe", "debug"),
            ("debug", "testlib", "debug-testlib"),
        ],
    )
    def test_build_dirname(self, build_type, kind, expected):
        assert get_build_dirname(build_type, kind) == expected

    @pytest.mark.parametrize("march", VALID_MARCHES)
    def test_validate_march_accepts(self, march):
        assert validate_march(march) == march

    @pytest.mark.parametrize("march", INVALID_MARCHES)
    def test_validate_march_rejects(self, march):
        with pytest.raises(ValueError, match="invalid --march value"):
            validate_march(march)

    @pytest.mark.parametrize("march", INVALID_MARCHES)
    def test_invalid_march_is_rejected_everywhere(self, march):
        # we never try to "sanitize" a value: the cflags and the name of the
        # build dir must not be able to smuggle anything
        with pytest.raises(ValueError, match="invalid --march value"):
            get_cflags("native", "release", march=march)


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
# 2. CompilerConfig wiring (the libspy build is stubbed out)
# ======================================================================


@pytest.fixture
def ensure_calls(monkeypatch, tmpdir):
    """
    Replace CompilerConfig._ensure_libspy_built with a recorder, so that we can
    inspect the flags without ever building libspy.
    """

    class Calls(list):
        libdir = py.path.local(tmpdir).join("fake-libdir")

    calls = Calls()
    libdir = calls.libdir

    def fake(*args):
        calls.append(args)
        return libdir

    monkeypatch.setattr(CompilerConfig, "_ensure_libspy_built", staticmethod(fake))
    return calls


def linked_libdir(comp: CompilerConfig) -> str:
    return comp.ldflags[comp.ldflags.index("-L") + 1]


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
        # we link against the libspy returned by _ensure_libspy_built
        assert linked_libdir(comp) == str(ensure_calls.libdir)
        assert ensure_calls == [("native", "release", "exe", "x86-64-v3")]

    def test_no_march(self, ensure_calls):
        cfg = BuildConfig(target="native", kind="exe", build_type="release", gc="none")
        comp = CompilerConfig(cfg)
        assert march_flags(comp.cflags) == []
        assert ensure_calls == [("native", "release", "exe", None)]

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


class TestEnsureLibspyBuilt:
    def test_no_march_uses_the_libspy_built_by_make(self, monkeypatch):
        def no_build(*args):
            raise AssertionError("libspy must not be built without --march")

        monkeypatch.setattr("spy.libspy.builder.ensure_libspy", no_build)
        libdir = CompilerConfig._ensure_libspy_built("native", "release", "exe", None)
        assert libdir == py.path.local(get_libdir("native", "release", "exe"))

    def test_march_uses_ensure_libspy(self, monkeypatch, tmpdir):
        calls = []

        def fake(*args):
            calls.append(args)
            return py.path.local(tmpdir)

        monkeypatch.setattr("spy.libspy.builder.ensure_libspy", fake)
        libdir = CompilerConfig._ensure_libspy_built(
            "native-static", "debug", "exe", "native"
        )
        assert libdir == py.path.local(tmpdir)
        assert calls == [("native-static", "debug", "exe", "native")]


# ======================================================================
# 3. CLI validation
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
# 4. real end-to-end builds
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
        libdir = ensure_libspy("native", "release", "exe", march)  # cached
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
        libdir = ensure_libspy("native-static", "debug", "exe", "native")  # cached
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
        cache = libspy_builder.cache_dir()
        res = invoke_build(tmpdir, main_spy, "--gc", "none", "--march", bogus)
        assert res.exit_code == 2
        assert not cache.check() or not list(cache.visit(f"*-march-{bogus}-*"))
