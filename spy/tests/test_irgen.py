from typing import Any
import textwrap
import pytest
import spy.ast
from spy.parser import Parser
from spy.errors import SPyTypeError, SPyCompileError
from spy.irgen.symtable import Symbol
from spy.irgen.typechecker import TypeChecker
from spy.irgen.modgen import ModuleGen
from spy.vm.vm import SPyVM
from spy.vm.function import W_FunctionType
from spy.util import Color
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

    def expect_error(self, src: str) -> SPyCompileError:
        """
        Same as compile(), but expect that the compilation fails and return the
        raised SPyCompileError.

        Note, this RETURNS the error, it does not RAISE it.
        Then, you can assert more details about the error by using .match().
        """
        with pytest.raises(SPyCompileError) as exc:
            self.compile(src)
        return exc.value

    def match(self, err: SPyCompileError, *expected_msgs: str) -> bool:
        """
        Check whether all the given messages are present in the error, either as
        the main message or in the annotations.
        """
        all_messages = [err.message] + [ann.message for ann in err.annotations]
        for expected in expected_msgs:
            if expected not in all_messages:
                expected = Color.set('yellow', expected)
                print('Error match failed!')
                print('The following error message was expected but not found:')
                print(f'  - {expected}')
                print()
                print('Captured error')
                formatted_error = err.format(use_colors=True)
                print(textwrap.indent(formatted_error, '    '))
                pytest.fail(f'Error message not found: {expected}')
        return True

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
            '@return': Symbol('@return', w_i32, ANYLOC),
        }
        #
        # codegen tests
        w_foo = w_mod.content.get('foo')
        w_result = vm.call_function(w_foo, [])
        assert vm.unwrap(w_result) == 42

    def test_resolve_type_errors(self):
        with pytest.raises(SPyTypeError,
                           match='only simple types are supported for now'):
            self.compile("""
            def foo() -> MyList[i32]:
                return 42
            """)
        #
        with pytest.raises(SPyTypeError, match='cannot find type `aaa`'):
            self.compile("""
            def foo() -> aaa:
                return 42
            """)
        #
        self.vm.builtins.w_I_am_not_a_type = self.vm.wrap(42)  # type: ignore
        with pytest.raises(SPyTypeError, match='I_am_not_a_type is not a type'):
            self.compile("""
            def foo() -> I_am_not_a_type:
                return 42
            """)

    def test_wrong_return_type(self):
        err = self.expect_error("""
        def foo() -> str:
            return 42
        """)
        assert self.match(
            err,
            'mismatched types',
            'expected `str`, got `i32`',
            'expected `str` because of return type',
        )

    def test_local_variables(self):
        w_mod = self.compile(
        """
        def foo() -> i32:
            x: i32 = 42
            return x
        """, only_typecheck=True)
        vm = self.vm
        w_i32 = vm.builtins.w_i32
        #
        # typechecker tests
        funcdef = self.get_funcdef('foo')
        w_functype, scope = self.t.get_funcdef_info(funcdef)
        assert scope.symbols == {
            '@return': Symbol('@return', w_i32, ANYLOC),
            'x': Symbol('x', w_i32, ANYLOC),
        }
        #
        # codegen tests
        ## w_foo = w_mod.content.get('foo')
        ## w_result = vm.call_function(w_foo, [])
        ## assert vm.unwrap(w_result) == 42
