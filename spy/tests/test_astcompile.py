import textwrap
from typing import Optional

import pytest

from spy.analyze.importing import ImportAnalyzer
from spy.backend.spy import AST_FORMAT, FQN_FORMAT, SPyBackend
from spy.fqn import FQN
from spy.util import print_diff
from spy.vm.function import W_ASTFunc
from spy.vm.vm import SPyVM


@pytest.mark.usefixtures("init")
class TestASTCompile:
    @pytest.fixture
    def init(self, tmpdir):
        self.tmpdir = tmpdir
        self.vm = SPyVM()
        self.vm.path.append(str(self.tmpdir))

    def compile_src(self, src: str) -> None:
        """
        Compile source code without redshifting, to test astcompile output.
        """
        f = self.tmpdir.join("test.spy")
        src = textwrap.dedent(src)
        f.write(src)
        self.vm.import_("test")

    def write_src(self, src: str) -> None:
        """
        Write source code to test.spy without importing.
        """
        f = self.tmpdir.join("test.spy")
        src = textwrap.dedent(src)
        f.write(src)

    def assert_dump(
        self,
        expected: str,
        *,
        fqn_format: FQN_FORMAT = "short",
        ast_format: AST_FORMAT = "short",
        funcname: Optional[str] = None,
    ) -> None:
        b = SPyBackend(self.vm, fqn_format=fqn_format, ast_format=ast_format)
        if funcname is not None:
            fqn = FQN(f"test::{funcname}")
            w_func = self.vm.globals_w[fqn]
            assert isinstance(w_func, W_ASTFunc)
            b.modname = "test"
            b.dump_w_func(fqn, w_func)
            got = b.out.build().strip()
        else:
            got = b.dump_mod("test").strip()
        expected = textwrap.dedent(expected).strip()
        if got != expected:
            print_diff(expected, got, "expected", "got")
            pytest.fail("assert_dump failed")

    def assert_dump_decls(
        self,
        expected: str,
        *,
        ast_format: AST_FORMAT = "short",
    ) -> None:
        """
        Dump all declarations using emit_decl, like the CLI does.
        """
        importer = ImportAnalyzer(self.vm, "test", use_spyc=False)
        importer.astcompile_all()
        mod = importer.getmod("test")
        b = SPyBackend(self.vm, ast_format=ast_format)
        b.modname = "test"
        for decl in mod.decls:
            b.emit_decl(decl)
            b.out.wl()
        got = b.out.build().strip()
        expected = textwrap.dedent(expected).strip()
        if got != expected:
            print_diff(expected, got, "expected", "got")
            pytest.fail("assert_dump_decls failed")

    def test_name_lowered_to_nameerror(self):
        self.compile_src("""
        def foo() -> i32:
            return undefined_name
        """)
        expected = """
        def foo() -> i32:
            return NameError(undefined_name)
        """
        self.assert_dump(expected, ast_format="full")

    def test_for(self):
        self.compile_src("""
        def foo(lst: dynamic) -> None:
            for i in lst:
                print(i)
        """)
        expected = """
        def foo(lst: dynamic) -> None:
            _$iter0 = lst.__fastiter__()
            while _$iter0.__continue_iteration__():
                i = _$iter0.__item__()
                _$iter0 = _$iter0.__next__()
                print(i)
        """
        self.assert_dump(expected)

    def test_local_direct(self):
        self.compile_src("""
        def foo(x: i32) -> i32:
            y = x
            return y
        """)
        expected = """
        def foo(x: i32) -> i32:
            AssignLocal(y := LocalDirect(x))
            return LocalDirect(y)
        """
        self.assert_dump(expected, ast_format="full")

    def test_import_ref(self):
        self.compile_src("""
        def foo() -> None:
            print('hello')
        """)
        expected = """
        def foo() -> None:
            ImportRef(print)('hello')
        """
        self.assert_dump(expected, ast_format="full")

    def test_outer_cell(self):
        self.compile_src("""
        var x: i32 = 0
        def foo() -> i32:
            x = 1
            return x
        """)
        expected = """
        def foo() -> i32:
            AssignCell(x := 1)
            return OuterCell(x)
        """
        self.assert_dump(expected, ast_format="full", funcname="foo")

    def test_outer_direct(self):
        self.compile_src("""
        def outer() -> dynamic:
            x = 1
            def inner() -> i32:
                return x
            return inner
        """)
        expected = """
        def outer() -> dynamic:
            AssignLocal(x := 1)
            def inner() -> ImportRef(i32):
                return OuterDirect(x)
            return LocalDirect(inner)
        """
        self.assert_dump(expected, ast_format="full", funcname="outer")

    def test_global_vardef(self):
        self.write_src("""
        var x: i32 = 42
        def foo() -> i32:
            return x
        """)
        expected = """
        var x: i32 = 42

        def foo() -> i32:
            return x
        """
        self.assert_dump_decls(expected)
