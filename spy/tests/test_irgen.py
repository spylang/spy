from typing import Any
import textwrap
import pytest
import spy.ast
from spy.parser import Parser
from spy.errors import SPyCompileError
from spy.irgen.symtable import Symbol
from spy.irgen.typechecker import TypeChecker
from spy.irgen.modgen import ModuleGen
from spy.vm.vm import SPyVM
from spy.vm.function import W_FunctionType
from spy.tests.support import CompilerTest

class AnyLocClass:
    def __eq__(self, other):
        return True
ANYLOC: Any = AnyLocClass()

class TestIRGen(CompilerTest):

    def compile(self, src: str, *, only_typecheck: bool = False):
        """
        Compile the given src code into a W_Module
        """
        srcfile = self.write_source('test.py', src)
        self.p = Parser.from_filename(str(srcfile))
        self.mod = self.p.parse()
        self.t = TypeChecker(self.vm, self.mod)
        self.t.check_everything()
        if not only_typecheck:
            self.modgen = ModuleGen(self.vm, self.t, self.mod)
            return self.modgen.make_w_mod()

    def expect_errors(self, src: str, *, errors: list[str]) -> SPyCompileError:
        """
        Expect that compile() fails, and check that the expected errors are
        reported
        """
        return self._do_expect_errors('compile', src, errors=errors)

    def get_funcdef(self, name: str) -> spy.ast.FuncDef:
        for decl in self.mod.decls:
            if isinstance(decl, spy.ast.FuncDef) and decl.name == name:
                return decl
        raise KeyError(name)

    def test_simple(self):
        w_mod = self.compile(
        """
        def foo() -> i32:
            return 42
        """)
        vm = self.vm
        w_i32 = vm.builtins.w_i32
        #
        # typechecker tests
        funcdef = self.get_funcdef('foo')
        w_expected_functype = W_FunctionType([], w_i32)
        w_functype, scope = self.t.get_funcdef_info(funcdef)
        assert w_functype == w_expected_functype
        assert scope.symbols == {
            '@return': Symbol('@return', w_i32, ANYLOC, scope),
        }
        #
        # codegen tests
        w_foo = w_mod.content.get('foo')
        w_result = vm.call_function(w_foo, [])
        assert vm.unwrap(w_result) == 42

    def test_resolve_type_errors(self):
        self.expect_errors(
            """
            def foo() -> MyList[i32]:
                return 42
            """,
            errors = [
                'only simple types are supported for now'
            ])

        self.expect_errors(
            """
            def foo() -> aaa:
                return 42
            """,
            errors = [
                'cannot find type `aaa`'
            ])

        self.vm.builtins.w_I_am_not_a_type = self.vm.wrap(42)  # type: ignore
        self.expect_errors(
            """
            def foo() -> I_am_not_a_type:
                return 42
            """,
            errors = [
                'I_am_not_a_type is not a type'
            ])

    def test_wrong_return_type(self):
        self.expect_errors(
            """
            def foo() -> str:
                return 42
            """,
            errors = [
                'mismatched types',
                'expected `str`, got `i32`',
                'expected `str` because of return type',
            ])

    def test_local_variables(self):
        w_mod = self.compile(
        """
        def foo() -> i32:
            x: i32 = 42
            return x
        """)
        vm = self.vm
        w_i32 = vm.builtins.w_i32
        #
        # typechecker tests
        funcdef = self.get_funcdef('foo')
        w_functype, scope = self.t.get_funcdef_info(funcdef)
        assert scope.symbols == {
            '@return': Symbol('@return', w_i32, ANYLOC, scope),
            'x': Symbol('x', w_i32, ANYLOC, scope),
        }
        #
        # codegen tests
        w_foo = w_mod.content.get('foo')
        w_result = vm.call_function(w_foo, [])
        assert vm.unwrap(w_result) == 42

    def test_declare_variable_errors(self):
        self.expect_errors(
            """
            def foo() -> i32:
                x: i32 = 1
                x: i32 = 2
            """,
            errors = [
                'variable `x` already declared',
                'this is the new declaration',
                'this is the previous declaration',
            ])
        #
        self.expect_errors(
            """
            def foo() -> i32:
                x: str = 1
            """,
            errors = [
                'mismatched types',
                'expected `str`, got `i32`',
                'expected `str` because of type declaration',
            ])
        #
        self.expect_errors(
            """
            def foo() -> i32:
                return x
            """,
            errors = [
                'cannot find variable `x` in this scope',
                'not found in this scope',
            ])

    def test_function_arguments(self):
        w_mod = self.compile(
        """
        def inc(x: i32) -> i32:
            return x + 1
        """)
        vm = self.vm
        w_i32 = vm.builtins.w_i32
        #
        # typechecker tests
        funcdef = self.get_funcdef('inc')
        w_expected_functype = W_FunctionType.make(x=w_i32, w_restype=w_i32)
        w_functype, scope = self.t.get_funcdef_info(funcdef)
        assert w_functype == w_expected_functype
        assert scope.symbols == {
            '@return': Symbol('@return', w_i32, ANYLOC, scope),
            'x': Symbol('x', w_i32, ANYLOC, scope),
        }
        #
        # codegen tests
        w_inc = w_mod.content.get('inc')
        w_x = vm.wrap(100)
        w_result = vm.call_function(w_inc, [w_x])
        assert vm.unwrap(w_result) == 101

    def test_assign(self):
        w_mod = self.compile(
        """
        def inc(x: i32) -> i32:
            res: i32 = 0
            res = x + 1
            return res
        """)
        vm = self.vm
        w_inc = w_mod.content.get('inc')
        w_x = vm.wrap(100)
        w_result = vm.call_function(w_inc, [w_x])
        assert vm.unwrap(w_result) == 101
