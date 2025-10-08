import pytest
import textwrap
from spy.vm.function import W_ASTFunc
from spy.backend.spy import SPyBackend
from spy.util import print_diff
from spy.tests.support import CompilerTest, only_interp

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
            x: i32
            x = 1
            y: f64
            y = 2.0
        """)

    def test_implicit_declaration(self):
        self.backend = "doppler"
        mod = self.compile("""
        def foo() -> None:
            x: i32 = 1
            y = 2.0
        """)
        self.assert_dump("""
        def foo() -> None:
            x: i32
            x = 1
            y: f64
            y = 2.0
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
        def foo() -> list[i32]:
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
        from unsafe import ptr

        def foo(p: ptr[i32]) -> None:
            pass
        """
        expected = """
        def foo(p: `unsafe::ptr[i32]`) -> None:
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

    def test_zz_sanity_check(self):
        """
        This is a hack.

        We want to be sure that the SPy backend is able to format all AST
        supported AST nodes.

        This is a smoke test to run the SPy backend on ALL SPy sources which
        were passed to CompilerTest.compile() during the test run.

        It is super-important that this file is run AFTER the tests in
        tests/compiler, else CompilerTest.ALL_COMPILED_SOURCES would be
        empty. This is ensured by (another) hack inside tests/conftest.py.

        If this sanity check fails, the proper action to take is to write an
        unit test for the missing AST node.
        """
        b = SPyBackend(self.vm)
        sources = list(CompilerTest.ALL_COMPILED_SOURCES)
        for i, src in enumerate(sources):
            modname = f"test_backend_spy_{i}"
            mod = self.compile(src, modname=modname)
            for fqn, w_obj in self.vm.fqns_by_modname(modname):
                if isinstance(w_obj, W_ASTFunc) and w_obj.funcdef.color == "red":
                    try:
                        b.dump_w_func(fqn, w_obj)
                    except NotImplementedError as exc:
                        print(src)
                        pytest.fail(str(exc))
