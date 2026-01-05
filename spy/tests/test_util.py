import os
from typing import Any, no_type_check

import py.path
import pytest

from spy.util import (
    ANYTHING,
    OrderedSet,
    cleanup_spyc_files,
    extend,
    func_equals,
    magic_dispatch,
    shortrepr,
)


def test_ANYTHING():
    assert ANYTHING == 1
    assert 1 == ANYTHING
    assert ANYTHING == ANYTHING
    assert not ANYTHING != 1
    assert not 1 != ANYTHING
    assert not ANYTHING != ANYTHING


def test_OrderedSet():
    s = OrderedSet[int]()
    s.add(3)
    s.add(1)
    s.add(2)
    s.add(1)  # duplicate

    # test contains
    assert 3 in s
    assert 1 in s
    assert 2 in s
    assert 999 not in s

    # test iteration preserves order and doesn't include duplicates
    assert list(s) == [3, 1, 2]


def test_magic_dispatch():
    class Foo:
        def visit(self, obj: Any, arg: int) -> Any:
            return magic_dispatch(self, "visit", obj, arg)

        def visit_int(self, x: int, y: int) -> int:
            return x + y

        def visit_str(self, s: str, n: int) -> str:
            return s.upper() * n

    f = Foo()
    assert f.visit(4, 5) == 9
    assert f.visit("bar-", 3) == "BAR-BAR-BAR-"
    with pytest.raises(NotImplementedError, match="visit_float"):
        f.visit(1.0, -1)


def test_magic_dispatch_NotImplemented():
    class Foo:
        def visit(self, obj: Any, arg: int) -> Any:
            return magic_dispatch(self, "visit", obj, arg)

        def visit_int(self, x: int, y: int) -> int:
            return x + y

        def visit_NotImplemented(self, obj: Any, arg: int) -> Any:
            return f"hello NotImplemented {obj} {arg}"

    f = Foo()
    assert f.visit(4, 5) == 9
    assert f.visit("world", 42) == "hello NotImplemented world 42"


def test_extend():
    class Foo:
        pass

    @extend(Foo)
    class Foo2:
        X = 100

        def meth(self):
            return 42

    assert Foo2 is Foo
    assert Foo.X == 100  # type: ignore
    assert Foo().meth() == 42  # type: ignore


def test_extend_dont_overwrite():
    class Foo:
        X = 42

    with pytest.raises(TypeError, match="class Foo has already a member 'X'"):

        @extend(Foo)
        class Foo2:
            X = 100


def test_shortrepr():
    s = "12345678"
    assert shortrepr(s, 10) == "'12345678'"
    assert shortrepr(s, 8) == "'12345678'"
    assert shortrepr(s, 7) == "'12345...'"


# ======= tests for same_closure =======


class Test_func_equals:
    def test_identity(self):
        def f() -> None:
            pass

        assert func_equals(f, f)

    def test_different_code_objects(self):
        def f():
            pass

        def g():
            pass

        assert not func_equals(f, g)

    def test_no_defaults(self):
        @no_type_check
        def make(n):
            def fn(x=n):
                pass

            return fn

        f0 = make(0)
        f1 = make(1)
        with pytest.raises(ValueError, match="unsupported: default arguments"):
            func_equals(f0, f1)

    def test_no_kwdefaults(self):
        @no_type_check
        def make(n):
            def fn(*, x=n):
                pass

            return fn

        f0 = make(0)
        f1 = make(1)
        with pytest.raises(
            ValueError, match="unsupported: kwargs with default arguments"
        ):
            func_equals(f0, f1)

    def test_closure(self):
        @no_type_check
        def make(n):
            def fn():
                return n

            return fn

        f0 = make(0)
        f1 = make(1)
        f0b = make(0)
        assert not func_equals(f0, f1)
        assert func_equals(f0, f0b)


# ======= tests for cleanup_spyc_files =======


class Test_cleanup_spyc_files:
    def test_cleanup_basic(self, tmpdir, capsys):
        tmpdir = py.path.local(tmpdir)
        pycache = tmpdir.join("__pycache__")
        pycache.mkdir()
        spyc1 = pycache.join("mod1.spyc")
        spyc2 = pycache.join("mod2.spyc")
        spyc1.write("")
        spyc2.write("")

        cleanup_spyc_files(tmpdir, verbose=True)

        assert not spyc1.exists()
        assert not spyc2.exists()
        captured = capsys.readouterr()
        assert "2 file(s) removed" in captured.out

    def test_cleanup_with_subdirectories(self, tmpdir, capsys):
        tmpdir = py.path.local(tmpdir)

        # Create nested __pycache__ directories
        pycache1 = tmpdir.join("__pycache__")
        pycache1.mkdir()
        spyc1 = pycache1.join("main.spyc")
        spyc1.write("")

        subdir = tmpdir.join("subdir")
        subdir.mkdir()
        pycache2 = subdir.join("__pycache__")
        pycache2.mkdir()
        spyc2 = pycache2.join("module.spyc")
        spyc2.write("")

        cleanup_spyc_files(tmpdir, verbose=True)

        assert not spyc1.exists()
        assert not spyc2.exists()
        captured = capsys.readouterr()
        assert "2 file(s) removed" in captured.out

    def test_cleanup_no_files(self, tmpdir, capsys):
        tmpdir = py.path.local(tmpdir)

        cleanup_spyc_files(tmpdir, verbose=True)

        captured = capsys.readouterr()
        assert "No .spyc files found" in captured.out

    def test_cleanup_with_permission_errors(self, tmpdir, capsys):
        tmpdir = py.path.local(tmpdir)

        # Create __pycache__ with a .spyc file we can delete
        pycache = tmpdir.join("__pycache__")
        pycache.mkdir()
        spyc1 = pycache.join("accessible.spyc")
        spyc1.write("")

        # Create a subdirectory with another __pycache__
        subdir = tmpdir.join("subdir")
        subdir.mkdir()
        subdir_pycache = subdir.join("__pycache__")
        subdir_pycache.mkdir()
        spyc2 = subdir_pycache.join("inaccessible.spyc")
        spyc2.write("")

        # Make the subdirectory inaccessible
        os.chmod(str(subdir), 0o000)

        try:
            cleanup_spyc_files(tmpdir, verbose=True)

            # Should still remove the accessible file
            assert not spyc1.exists()

            captured = capsys.readouterr()
            # Should report that 1 file was removed
            assert "1 file(s) removed" in captured.out
            # Should report permission error
            assert "Permission denied" in captured.out
        finally:
            # Restore permissions for cleanup
            os.chmod(str(subdir), 0o755)

    def test_cleanup_not_a_directory(self, tmpdir, capsys):
        tmpdir = py.path.local(tmpdir)
        file_path = tmpdir.join("not_a_dir.txt")
        file_path.write("content")

        cleanup_spyc_files(file_path, verbose=True)

        captured = capsys.readouterr()
        assert "not a directory" in captured.out

    def test_cleanup_non_verbose(self, tmpdir, capsys):
        tmpdir = py.path.local(tmpdir)
        pycache = tmpdir.join("__pycache__")
        pycache.mkdir()
        spyc1 = pycache.join("test.spyc")
        spyc1.write("")

        cleanup_spyc_files(tmpdir, verbose=False)

        assert not spyc1.exists()
        captured = capsys.readouterr()
        # Should not print anything when not verbose
        assert captured.out == ""
