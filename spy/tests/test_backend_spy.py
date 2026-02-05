import textwrap
import traceback

import pytest

from spy.backend.spy import SPyBackend
from spy.tests.support import CompilerTest, only_interp
from spy.util import print_diff
from spy.vm.function import W_ASTFunc
from spy.vm.vm import SPyVM


def run_sanity_check_fixture(tmpdir_factory):
    """
    Run SPy backend sanity check at the end of the test session.

    This is called by the fixture in conftest.py. It checks all sources
    compiled during the test run and fails if any unsupported AST nodes
    are found.
    """
    sources = list(CompilerTest.ALL_COMPILED_SOURCES)
    if not sources:
        return

    tmpdir = tmpdir_factory.mktemp("spy_backend_sanity_check")
    vm = SPyVM()
    vm.path.append(str(tmpdir))
    b = SPyBackend(vm)

    for i, src in enumerate(sources):
        modname = f"test_backend_spy_{i}"
        src = textwrap.dedent(src)
        srcfile = tmpdir.join(f"{modname}.spy")
        srcfile.write(src)

        try:
            vm.import_(modname)
        except Exception:
            continue

        for fqn, w_obj in vm.fqns_by_modname(modname):
            if isinstance(w_obj, W_ASTFunc) and w_obj.funcdef.color == "red":
                try:
                    b.dump_w_func(fqn, w_obj)
                except NotImplementedError as exc:
                    tb = traceback.extract_tb(exc.__traceback__)
                    tb_lines = traceback.format_list(tb[-4:])

                    print()
                    print("=" * 70)
                    print("SPy Backend Sanity Check FAILED")
                    print("=" * 70)
                    print("Traceback (last 4 entries):")
                    for line in tb_lines:
                        print(line, end="")
                    print(f"\033[91m{exc.__class__.__name__}: {exc}\033[0m")
                    print()
                    print("Source code that triggered the error:")
                    print(src)
                    print("=" * 70)
                    pytest.fail(f"SPy backend sanity check failed: {exc}")


@only_interp
class TestSPyBackend(CompilerTest):
    def assert_dump(self, expected: str, *, modname: str = "test") -> None:
        b = SPyBackend(self.vm)
        got = b.dump_mod(modname).strip()
        expected = textwrap.dedent(expected).strip()
        if got != expected:
            print_diff(expected, got, "expected", "got")
            pytest.fail("assert_dump failed")

    def test_simple(self):
        mod = self.compile("""
        def foo() -> i32:
            pass
        """)
        self.assert_dump("""
        def foo() -> i32:
            pass
        """)

    def test_args_and_return(self):
        mod = self.compile("""
        def foo(x: i32, y: i32) -> i32:
            return 42
        """)
        self.assert_dump("""
        def foo(x: i32, y: i32) -> i32:
            return 42
        """)

    def test_expr_precedence(self):
        mod = self.compile("""
        def foo() -> None:
            a = 1 + 2 * 3
            b = 1 + (2 * 3)
            c = (1 + 2) * 3
        """)
        self.assert_dump("""
        def foo() -> None:
            a = 1 + 2 * 3
            b = 1 + 2 * 3
            c = (1 + 2) * 3
        """)

    def test_bool_ops(self):
        mod = self.compile("""
        def foo(a: bool, b: bool, c: bool) -> bool:
            return a and b or c

        def bar(a: bool, b: bool, c: bool) -> bool:
            return a or (b and c)

        def baz(a: bool, b: bool, c: bool) -> bool:
            return a or b or c

        def qux(a: bool, b: bool, c: bool) -> bool:
            return a and b and c
        """)
        self.assert_dump("""
        def foo(a: bool, b: bool, c: bool) -> bool:
            return a and b or c

        def bar(a: bool, b: bool, c: bool) -> bool:
            return a or b and c

        def baz(a: bool, b: bool, c: bool) -> bool:
            return a or b or c

        def qux(a: bool, b: bool, c: bool) -> bool:
            return a and b and c
        """)

    def test_assignexpr_expr(self):
        mod = self.compile("""
        def foo() -> i32:
            return (x := 1)
        """)
        self.assert_dump("""
        def foo() -> i32:
            return x := 1
        """)

    def test_binop(self):
        mod = self.compile(r"""
        def foo() -> None:
            a + b
            a - b
            a * b
            a / b
            a // b
            a % b
            a << b
            a >> b
            a & b
            a | b
            a ^ b
            -a
        """)
        self.assert_dump(r"""
        def foo() -> None:
            a + b
            a - b
            a * b
            a / b
            a // b
            a % b
            a << b
            a >> b
            a & b
            a | b
            a ^ b
            -a
        """)

    def test_vardef(self):
        mod = self.compile("""
        def foo() -> None:
            x: i32 = 1
            y: f64 = 2.0
        """)
        self.assert_dump("""
        def foo() -> None:
            x: i32 = 1
            y: f64 = 2.0
        """)

    def test_implicit_declaration(self):
        self.backend = "doppler"
        mod = self.compile("""
        def foo() -> None:
            var x: i32 = 1
            var y = 2.0
        """)
        self.assert_dump("""
        def foo() -> None:
            x: i32 = 1
            y: f64 = 2.0
        """)

    def test_dont_dump_blue_func(self):
        """
        The primary use case for the SPy backend is to show what happens after
        redshift, so @blue funcs should not be dumped.
        """
        mod = self.compile("""
        @blue
        def GET_X():
            return 42

        def foo() -> None:
            pass
        """)
        self.assert_dump("""
        def foo() -> None:
            pass
        """)

    def test_func_aliases(self):
        mod = self.compile("""
        @blue.generic
        def add(T):
            def impl(x: T, y: T) -> T:
                return x + y
            return impl

        add_i32 = add[i32]
        add_f64 = add[f64]

        def foo() -> None:
            add_i32(1, 2)
            add_f64(3.4, 5.6)
        """)
        self.assert_dump("""
        add_i32 = `test::add[i32]::impl`
        add_f64 = `test::add[f64]::impl`

        def `test::add[i32]::impl`(x: i32, y: i32) -> i32:
            return x + y

        def `test::add[f64]::impl`(x: f64, y: f64) -> f64:
            return x + y

        def foo() -> None:
            add_i32(1, 2)
            add_f64(3.4, 5.6)
        """)

    def test_while(self):
        src = """
        def foo() -> None:
            while 1:
                pass
        """
        self.compile(src)
        self.assert_dump(src)

    def test_FuncDef(self):
        src = """
        def outer() -> None:
            def inner(x: i32, y: i32) -> None:
                pass
        """
        self.compile(src)
        self.assert_dump(src)

    def test_call(self):
        src = """
        def add(x: i32, y: i32) -> i32:
            return x + y

        def foo() -> i32:
            return add(x, y)
        """
        self.compile(src)
        self.assert_dump(src)

    def test_callmethod(self):
        src = """
        def foo() -> i32:
            return x.bar(1, 2, 3)
        """
        self.compile(src)
        self.assert_dump(src)

    def test_getitem(self):
        src = """
        def foo() -> None:
            return x[i, 1]
        """
        self.compile(src)
        self.assert_dump(src)

    def test_setitem(self):
        src = """
        def foo() -> None:
            x[i, 1] = 0
        """
        self.compile(src)
        self.assert_dump(src)

    def test_getattr(self):
        src = """
        def foo() -> None:
            return x.foo
        """
        self.compile(src)
        self.assert_dump(src)

    def test_setattr(self):
        src = """
        def foo() -> None:
            x.foo = 42
        """
        self.compile(src)
        self.assert_dump(src)

    def test_if(self):
        src = """
        def foo() -> None:
            if 1:
                aaa
            if 2:
                bbb
            else:
                ccc
        """
        self.compile(src)
        self.assert_dump(src)

    def test_list_literal(self):
        src = """
        def foo() -> dynamic:
            return [1, 2, 3]
        """
        self.compile(src)
        self.assert_dump(src)

    def test_tuple_literal(self):
        src = """
        def foo() -> tuple:
            return (1, 2, 3)
        """
        self.compile(src)
        self.assert_dump(src)

    def test_slice(self):
        src = """
        def foo() -> dynamic:
            return [1, 2, 3][:1:-1]
        """
        self.compile(src)
        self.assert_dump(src)

    def test_unpack_assign(self):
        src = """
        def foo() -> None:
            a, b, c = x
        """
        self.compile(src)
        self.assert_dump(src)

    def test_aug_assign(self):
        src = """
        def foo() -> None:
            x += 1
        """
        self.compile(src)
        self.assert_dump(src)

    def test_ptr(self):
        src = """
        from unsafe import raw_ptr

        def foo(p: raw_ptr[i32]) -> None:
            pass
        """
        expected = """
        def foo(p: `unsafe::raw_ptr[i32]`) -> None:
            pass
        """
        self.compile(src)
        self.assert_dump(expected)

    def test_classdef(self):
        src = """
        def foo() -> None:
            @struct
            class Point:
                x: i32
                y: i32
        """
        self.compile(src)
        self.assert_dump(src)

    def test_raise(self):
        src = """
        def foo() -> None:
            raise Exception('foo')
        """
        self.compile(src)
        self.assert_dump(src)

    def test_varargs(self):
        src = """
        def foo(a: i32, b: i32, *args: i32) -> i32:
            pass
        """
        self.compile(src)
        self.assert_dump(src)

    def test_dict_literal(self):
        src = """
        def foo() -> None:
            x = {10: 50, 60: 40}
        """
        self.compile(src)
        self.assert_dump(src)
