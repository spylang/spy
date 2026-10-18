"""
Tests for `spy build --march` and for the per-march libspy build.

They are organized from the cheapest to the most expensive:

  1. pure functions in spy.build.flags (no subprocess, no compiler)
  2. the libspy cache key (spy.libspy_build.cache_key)
  3. CompilerConfig wiring, with the libspy build stubbed out
  4. CompilerConfig._ensure_libspy_built and ensure_libspy, with ninja faked
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
from spy import libspy_build
from spy.build.config import BuildConfig, CompilerConfig
from spy.build.flags import (
    check_march,
    get_build_dirname,
    get_cflags,
    get_libdir,
    validate_march,
)
from spy.cli import app
from spy.errors import SPyError
from spy.libspy_build import cache_key, ensure_libspy

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
        with pytest.raises(ValueError, match="invalid --march value"):
            cache_key("native", "release", "exe", march)


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
# 2. the libspy cache key
# ======================================================================


@pytest.fixture
def libspy_copy(monkeypatch, tmpdir):
    """
    Work on a copy of the libspy sources, so that tests can edit them.
    """
    src = spy.libspy.BUILD.dirpath()
    dst = py.path.local(tmpdir).join("libspy")
    for subdir in ("src", "include", "vendored"):
        shutil.copytree(src.join(subdir), dst.join(subdir))
    monkeypatch.setattr(spy.libspy, "BUILD", dst.join("build"))
    return dst


class TestCacheKey:
    def test_deterministic(self):
        k1 = cache_key("native", "release", "exe", "native")
        k2 = cache_key("native", "release", "exe", "native")
        assert k1 == k2
        assert re.fullmatch(r"[0-9a-f]{16}", k1)

    def test_depends_on_the_variant(self):
        keys = {
            cache_key("native", "release", "exe", "native"),
            cache_key("native", "debug", "exe", "native"),
            cache_key("native", "release", "exe", "x86-64-v3"),
            cache_key("native", "release", "exe", "x86-64-v2"),
        }
        assert len(keys) == 4

    @pytest.mark.parametrize("filename", ["src/str.c", "include/spy.h"])
    def test_depends_on_the_sources(self, libspy_copy, filename):
        k1 = cache_key("native", "release", "exe", "native")
        with libspy_copy.join(filename).open("a") as f:
            f.write("\n/* changed */\n")
        assert cache_key("native", "release", "exe", "native") != k1

    def test_ignores_other_files(self, libspy_copy):
        # e.g. the build/ and deps/ directories, which are not inputs
        k1 = cache_key("native", "release", "exe", "native")
        libspy_copy.join("build", "native", "x.c").write("int x;", ensure=True)
        libspy_copy.join("src", "README").write("hello")
        assert cache_key("native", "release", "exe", "native") == k1

    def test_depends_on_the_compiler_version(self, monkeypatch):
        k1 = cache_key("native", "release", "exe", "native")
        real_run = subprocess.run

        def fake_run(cmdline, *args, **kwargs):
            if cmdline[-1] == "--version":
                return subprocess.CompletedProcess(cmdline, 0, b"cc 99.9", b"")
            return real_run(cmdline, *args, **kwargs)

        monkeypatch.setattr(subprocess, "run", fake_run)
        assert cache_key("native", "release", "exe", "native") != k1


# ======================================================================
# 3. CompilerConfig wiring (the libspy build is stubbed out)
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


# ======================================================================
# 4. CompilerConfig._ensure_libspy_built and ensure_libspy (ninja is faked)
# ======================================================================


class FakeNinja:
    """
    Fake subprocess.run for ninja: records the invocations and, like the real
    one, leaves a libspy.a in the build dir. Other commands (the compiler
    version) are really run.
    """

    def __init__(self) -> None:
        self.cmdlines: list[list[str]] = []
        self.creates_libspy_a = True
        self.real_run = subprocess.run

    def __call__(self, cmdline: list[str], *args: Any, **kwargs: Any) -> Any:
        if "ninja" not in cmdline:
            return self.real_run(cmdline, *args, **kwargs)
        assert kwargs.get("check") is True
        self.cmdlines.append(cmdline)
        builddir = py.path.local(cmdline[cmdline.index("-C") + 1])
        if self.creates_libspy_a:
            builddir.ensure("libspy.a")
        return subprocess.CompletedProcess(cmdline, 0)


@pytest.fixture
def fake_ninja(monkeypatch, libspy_copy, tmpdir):
    # a private build dir, so that we never touch the real cache
    monkeypatch.setattr(
        spy.libspy, "BUILD", py.path.local(tmpdir).join("libspy", "build")
    )
    monkeypatch.setattr(
        "spy.libspy_build.get_libdir",
        lambda target, build_type, kind: str(
            spy.libspy.BUILD.join(target, get_build_dirname(build_type, kind))
        ),
    )
    fake = FakeNinja()
    monkeypatch.setattr(subprocess, "run", fake)
    return fake


class TestEnsureLibspyBuilt:
    def test_no_march_does_nothing(self, fake_ninja):
        # without --march we keep using the libspy built by `make -C spy/libspy`
        libdir = CompilerConfig._ensure_libspy_built("native", "release", "exe", None)
        assert libdir == py.path.local(get_libdir("native", "release", "exe"))
        assert fake_ninja.cmdlines == []

    def test_build_and_cache(self, fake_ninja):
        libdir = CompilerConfig._ensure_libspy_built(
            "native", "release", "exe", "x86-64-v3"
        )
        key = cache_key("native", "release", "exe", "x86-64-v3")
        assert libdir.basename == f"release-march-x86-64-v3-{key}"
        assert libdir.join("libspy.a").check(file=True)
        assert len(fake_ninja.cmdlines) == 1
        assert fake_ninja.cmdlines[0][:3] == [sys.executable, "-m", "ninja"]

        # the second time it is found in the cache
        libdir2 = CompilerConfig._ensure_libspy_built(
            "native", "release", "exe", "x86-64-v3"
        )
        assert libdir2 == libdir
        assert len(fake_ninja.cmdlines) == 1

    def test_build_ninja(self, fake_ninja, monkeypatch):
        # look at the generated build.ninja before it is renamed
        seen = []
        orig = fake_ninja.__call__

        def spying(cmdline, *args, **kwargs):
            if "ninja" in cmdline:
                builddir = py.path.local(cmdline[cmdline.index("-C") + 1])
                seen.append(builddir.join("build.ninja").read())
            return orig(cmdline, *args, **kwargs)

        monkeypatch.setattr(subprocess, "run", spying)
        ensure_libspy("native", "release", "exe", "x86-64-v3")
        (build_ninja,) = seen
        assert "-march=x86-64-v3" in build_ninja
        assert "-flto" in build_ninja
        assert "RYU_ONLY_64_BIT_OPS" in build_ninja
        assert "build libspy.a: ar" in build_ninja
        assert "str.c" in build_ninja
        assert "jsffi" not in build_ninja

    def test_rebuild_if_the_sources_change(self, fake_ninja, libspy_copy):
        """
        Regression test: libspy.a already being there does NOT mean that it is
        up to date. The sources are part of the cache key, so a change in
        libspy gives a new directory and a rebuild.
        """
        libdir1 = ensure_libspy("native", "release", "exe", "native")
        with libspy_copy.join("src", "str.c").open("a") as f:
            f.write("\n/* changed */\n")
        libdir2 = ensure_libspy("native", "release", "exe", "native")
        assert libdir1 != libdir2
        assert len(fake_ninja.cmdlines) == 2
        # the old one is left in place: cleaning the cache is a separate matter
        assert libdir1.check(dir=True)

    def test_different_march_different_dir(self, fake_ninja):
        d1 = ensure_libspy("native", "release", "exe", "native")
        d2 = ensure_libspy("native", "release", "exe", "x86-64-v3")
        assert d1 != d2
        assert d1.dirpath() == d2.dirpath()

    def test_static_target_is_forwarded(self, fake_ninja):
        libdir = ensure_libspy("native-static", "debug", "exe", "native")
        assert libdir.dirpath().basename == "native-static"

    def test_concurrent_build_finished_first(self, fake_ninja, monkeypatch):
        # another process renames its own build to the final dir while ours is
        # running: we must use the result of the other one, not fail
        orig = fake_ninja.__call__
        final = []

        def racing(cmdline, *args, **kwargs):
            res = orig(cmdline, *args, **kwargs)
            if "ninja" in cmdline:
                key = cache_key("native", "release", "exe", "native")
                d = py.path.local(libspy_build.get_libdir("native", "release", "exe"))
                other = d.dirpath().join(f"{d.basename}-march-native-{key}")
                other.ensure("libspy.a")
                other.join("from-other-process").write("")
                final.append(other)
            return res

        monkeypatch.setattr(subprocess, "run", racing)
        libdir = ensure_libspy("native", "release", "exe", "native")
        assert libdir == final[0]
        assert libdir.join("from-other-process").check()
        # and no temporary directory is left behind
        assert [p.basename for p in libdir.dirpath().listdir()] == [libdir.basename]

    @pytest.mark.parametrize("march", INVALID_MARCHES)
    def test_invalid_march_never_reaches_ninja(self, fake_ninja, march):
        with pytest.raises(ValueError, match="invalid --march value"):
            CompilerConfig._ensure_libspy_built("native", "release", "exe", march)
        assert fake_ninja.cmdlines == []

    def test_ninja_does_not_produce_libspy_a(self, fake_ninja):
        fake_ninja.creates_libspy_a = False
        with pytest.raises(SPyError, match="did not produce .*libspy.a") as exc:
            CompilerConfig._ensure_libspy_built("native", "release", "exe", "native")
        assert exc.value.etype == "W_WIP"

    def test_ninja_failure_propagates(self, monkeypatch, fake_ninja):
        def failing(cmdline, *args, **kwargs):
            if "ninja" in cmdline:
                raise subprocess.CalledProcessError(1, cmdline)
            return fake_ninja.real_run(cmdline, *args, **kwargs)

        monkeypatch.setattr(subprocess, "run", failing)
        with pytest.raises(subprocess.CalledProcessError):
            CompilerConfig._ensure_libspy_built("native", "release", "exe", "native")
        # nothing is left in the cache
        d = py.path.local(libspy_build.get_libdir("native", "release", "exe")).dirpath()
        assert not d.check() or d.listdir() == []


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
        parent = py.path.local(get_libdir("native", "debug", "exe")).dirpath()
        res = invoke_build(tmpdir, main_spy, "--gc", "none", "--march", bogus)
        assert res.exit_code == 2
        assert not parent.check() or not parent.listdir(f"*-march-{bogus}-*")
