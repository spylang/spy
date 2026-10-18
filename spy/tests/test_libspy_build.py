import re
import shutil
import subprocess
import sys
from typing import Any

import py.path
import pytest

import spy.libspy
from spy import libspy_build
from spy.build.flags import get_build_dirname
from spy.errors import SPyError
from spy.libspy_build import cache_key, ensure_libspy

IS_DARWIN = sys.platform == "darwin"

# these end up on a command line and in a directory name
INVALID_MARCHES = ["", "a b", "a;b", "../x", "-native", "$(x)", "a'b"]


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
    # the cache lives in the private copy too: we never touch the real one
    monkeypatch.setattr(
        "spy.libspy_build.get_libdir",
        lambda target, build_type, kind: str(
            spy.libspy.BUILD.join(target, get_build_dirname(build_type, kind))
        ),
    )
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
def fake_ninja(monkeypatch, libspy_copy):
    fake = FakeNinja()
    monkeypatch.setattr(subprocess, "run", fake)
    return fake


class TestEnsureLibspy:
    def test_build_and_cache(self, fake_ninja):
        libdir = ensure_libspy("native", "release", "exe", "x86-64-v3")
        key = cache_key("native", "release", "exe", "x86-64-v3")
        assert libdir.basename == f"release-march-x86-64-v3-{key}"
        assert libdir.join("libspy.a").check(file=True)
        assert len(fake_ninja.cmdlines) == 1
        assert fake_ninja.cmdlines[0][:3] == [sys.executable, "-m", "ninja"]

        # the second time it is found in the cache
        libdir2 = ensure_libspy("native", "release", "exe", "x86-64-v3")
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
            ensure_libspy("native", "release", "exe", march)
        assert fake_ninja.cmdlines == []

    def test_ninja_does_not_produce_libspy_a(self, fake_ninja):
        fake_ninja.creates_libspy_a = False
        with pytest.raises(SPyError, match="did not produce .*libspy.a") as exc:
            ensure_libspy("native", "release", "exe", "native")
        assert exc.value.etype == "W_WIP"

    def test_ninja_failure_propagates(self, monkeypatch, fake_ninja):
        def failing(cmdline, *args, **kwargs):
            if "ninja" in cmdline:
                raise subprocess.CalledProcessError(1, cmdline)
            return fake_ninja.real_run(cmdline, *args, **kwargs)

        monkeypatch.setattr(subprocess, "run", failing)
        with pytest.raises(subprocess.CalledProcessError):
            ensure_libspy("native", "release", "exe", "native")
        # nothing is left in the cache
        d = py.path.local(libspy_build.get_libdir("native", "release", "exe")).dirpath()
        assert not d.check() or d.listdir() == []


class TestRealBuild:
    @pytest.mark.skipif(IS_DARWIN, reason="-march=native varies with Apple clang")
    def test_build_with_ninja(self, libspy_copy):
        """
        No fake here: compile the real libspy with the real ninja, in the
        private copy.
        """
        libdir = ensure_libspy("native", "debug", "exe", "native")
        libspy_a = libdir.join("libspy.a")
        assert libspy_a.check(file=True)
        members = subprocess.run(
            ["ar", "t", str(libspy_a)], capture_output=True, text=True, check=True
        ).stdout.split()
        assert {"str.o", "bytes.o", "f2s.o", "d2s.o"} <= set(members)
        assert "-march=native" in libdir.join("build.ninja").read()

        # the second call finds it in the cache
        mtime = libspy_a.mtime()
        assert ensure_libspy("native", "debug", "exe", "native") == libdir
        assert libspy_a.mtime() == mtime

    def test_invalid_march_is_rejected_by_cache_key(self):
        with pytest.raises(ValueError, match="invalid --march value"):
            cache_key("native", "release", "exe", "a b")
