import pytest
import textwrap
from spy.vm.vm import SPyVM
from spy.vm.function import W_ASTFunc
from spy.backend.spy import SPyBackend
from spy.util import print_diff
from spy.tests.support import CompilerTest, only_interp

@only_interp
class TestSPyBackend(CompilerTest):

    def assert_dump(self, expected: str, *, modname: str = 'test') -> None:
        b = SPyBackend(self.vm)
        got = b.dump_mod(modname).strip()
        expected = textwrap.dedent(expected).strip()
        if got != expected:
            print_diff(expected, got, 'expected', 'got')
            pytest.fail('assert_dump failed')

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
        def foo() -> void:
            a = 1 + 2 * 3
            b = 1 + (2 * 3)
            c = (1 + 2) * 3
        """)
        self.assert_dump("""
        def foo() -> void:
            a = 1 + 2 * 3
            b = 1 + 2 * 3
            c = (1 + 2) * 3
        """)

    def test_vardef(self):
        mod = self.compile("""
        def foo() -> void:
            x: i32 = 1
        """)
        self.assert_dump("""
        def foo() -> void:
            x: i32
            x = 1
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

        def foo() -> void:
            pass
        """)
        self.assert_dump("""
        def foo() -> void:
            pass
        """)

    def test_while(self):
        src = """
        def foo() -> void:
            while 1:
                pass
        """
        self.compile(src)
        self.assert_dump(src)

    def test_FuncDef(self):
        src = """
        def outer() -> void:
            def inner(x: i32, y: i32) -> void:
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

    def test_getitem(self):
        src = """
        def foo() -> void:
            return x[i]
        """
        self.compile(src)
        self.assert_dump(src)

    def test_if(self):
        src = """
        def foo() -> void:
            if 1:
                aaa
            if 2:
                bbb
            else:
                ccc
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
            modname = f'test_backend_spy_{i}'
            mod = self.compile(src, modname=modname)
            for fqn, w_obj in mod.w_mod.items_w():
                if isinstance(w_obj, W_ASTFunc):
                    try:
                        b.dump_w_func(w_obj)
                    except NotImplementedError as exc:
                        print(src)
                        pytest.fail(str(exc))
