from typing import Any
import textwrap
import pytest
import spy.ast
from spy.parser import Parser
from spy.errors import SPyCompileError, SPyRuntimeAbort
from spy.irgen.symtable import Symbol
from spy.vm.vm import SPyVM
from spy.vm.function import W_FunctionType
from spy.util import ANYTHING
from spy.tests.support import CompilerTest, skip_backends

class TestBasic(CompilerTest):

    def get_funcdef(self, name: str) -> spy.ast.FuncDef:
        for decl in self.compiler.mod.decls:
            if isinstance(decl, spy.ast.FuncDef) and decl.name == name:
                return decl
        raise KeyError(name)

    @skip_backends('C')
    def test_simple(self):
        mod = self.compile(
        """
        def foo() -> i32:
            return 42
        """)
        vm = self.vm
        w_i32 = vm.builtins.w_i32
        w_expected_functype = W_FunctionType([], w_i32)
        #
        # typechecker tests
        t = self.compiler.t
        assert t.global_scope.symbols == {
            'foo': Symbol('foo', 'const', w_expected_functype,
                          loc = ANYTHING,
                          scope = t.global_scope)
        }
        #
        funcdef = self.get_funcdef('foo')
        w_expected_functype = W_FunctionType([], w_i32)
        w_functype, scope = t.get_funcdef_info(funcdef)
        assert w_functype == w_expected_functype
        assert scope.symbols == {
            '@return': Symbol('@return', 'var', w_i32, loc=ANYTHING, scope=scope)
        }
        #
        # codegen tests
        assert mod.foo() == 42

    @skip_backends('C')
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

    @skip_backends('C')
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

    @skip_backends('C')
    def test_local_variables(self):
        mod = self.compile(
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
        w_functype, scope = self.compiler.t.get_funcdef_info(funcdef)
        assert scope.symbols == {
            '@return': Symbol('@return', 'var', w_i32, loc=ANYTHING, scope=scope),
            'x': Symbol('x', 'var', w_i32, loc=ANYTHING, scope=scope),
        }
        #
        # codegen tests
        assert mod.foo() == 42

    @skip_backends('C')
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

    @skip_backends('C')
    def test_function_arguments(self):
        mod = self.compile(
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
        w_functype, scope = self.compiler.t.get_funcdef_info(funcdef)
        assert w_functype == w_expected_functype
        assert scope.symbols == {
            '@return': Symbol('@return', 'var', w_i32, loc=ANYTHING, scope=scope),
            'x': Symbol('x', 'var', w_i32, loc=ANYTHING, scope=scope),
        }
        #
        # codegen tests
        assert mod.inc(100) == 101

    @skip_backends('C')
    def test_assign(self):
        mod = self.compile(
        """
        def inc(x: i32) -> i32:
            res: i32 = 0
            res = x + 1
            return res
        """)
        assert mod.inc(100) == 101

    @skip_backends('C')
    def test_assign_errors(self):
        self.expect_errors(
            """
            def foo() -> void:
                x = 42
            """,
            errors = [
                'variable `x` is not declared',
                'hint: to declare a new variable, you can use: `x: i32 = ...`',
            ])
        #
        self.expect_errors(
            """
            def foo(x: str) -> void:
                x = 42
            """,
            errors = [
                'mismatched types',
                'expected `str`, got `i32`',
                'expected `str` because of type declaration',
            ])

    @skip_backends('C')
    def test_global_variables(self):
        mod = self.compile(
        """
        x: i32 = 42
        def get_x() -> i32:
            return x
        def set_x(newval: i32) -> void:
            x = newval
        """)
        vm = self.vm
        assert mod.x == 42
        assert mod.get_x() == 42
        mod.set_x(100)
        assert mod.x == 100
        assert mod.get_x() == 100

    @skip_backends('C')
    def test_i32_add(self):
        mod = self.compile("""
        N: i32 = 100
        def add(x: i32, y: i32) -> i32:
            return x + y
        """)
        assert mod.add(1, 2) == 3
        assert mod.N == 100

    @skip_backends('C')
    def test_i32_mul(self):
        mod = self.compile("""
        def mul(x: i32, y: i32) -> i32:
            return x * y
        """)
        assert mod.mul(3, 4) == 12

    @skip_backends('C')
    def test_void_return(self):
        mod = self.compile("""
        x: i32 = 0
        def foo() -> void:
            x = 1
            return
            x = 2

        def bar() -> void:
            x = 3
            return None
            x = 4
        """)
        mod.foo()
        assert mod.x == 1
        mod.bar()
        assert mod.x == 3

    @skip_backends('C')
    def test_implicit_return(self):
        mod = self.compile("""
        x: i32 = 0
        def implicit_return_void() -> void:
            x = 1

        def implicit_return_i32() -> i32:
            x = 3
            # ideally, we should detect this case at compile time.
            # For now, it is a runtime error.
        """)
        mod.implicit_return_void()
        assert mod.x == 1

        with pytest.raises(SPyRuntimeAbort,
                           match='reached the end of the function without a `return`'):
            mod.implicit_return_i32()


    @skip_backends('C')
    def test_BinOp_error(self):
        self.expect_errors(
            f"""
            def bar(a: i32, b: str) -> void:
                return a + b
            """,
            errors = [
                'cannot do `i32` + `str`',
                'this is `i32`',
                'this is `str`',
            ]
        )

    @skip_backends('C')
    def test_function_call(self):
        mod = self.compile("""
        def foo(x: i32, y: i32, z: i32) -> i32:
            return x*100 + y*10 + z

        def bar(y: i32) -> i32:
            return foo(y, y+1, y+2)
        """)
        assert mod.foo(1, 2, 3) == 123
        assert mod.bar(4) == 456

    @skip_backends('C')
    def test_function_call_errors(self):
        self.expect_errors(
            f"""
            inc: i32 = 0
            def bar() -> void:
                return inc(0)
            """,
            errors = [
                'cannot call objects of type `i32`',
                'this is not a function',
                'variable defined here'
            ]
        )
        #
        self.expect_errors(
            f"""
            def inc(x: i32) -> i32:
                return x+1
            def bar() -> void:
                return inc()
            """,
            errors = [
                'this function takes 1 argument but 0 arguments were supplied',
                '1 argument missing',
                'function defined here',
            ]
        )
        #
        self.expect_errors(
            f"""
            def inc(x: i32) -> i32:
                return x+1
            def bar() -> void:
                return inc(1, 2, 3)
            """,
            errors = [
                'this function takes 1 argument but 3 arguments were supplied',
                '2 extra arguments',
                'function defined here',
            ]
        )
        #
        self.expect_errors(
            f"""
            def inc(x: i32) -> i32:
                return x+1
            def bar(s: str) -> i32:
                return inc(s)
            """,
            errors = [
                'mismatched types',
                'expected `i32`, got `str`',
                'function defined here'
            ]
        )

    @skip_backends('C')
    def test_StmtExpr(self):
        mod = self.compile("""
        x: i32 = 0
        def inc() -> void:
            x = x + 1

        def foo() -> void:
            inc()
            inc()
        """)
        mod.foo()
        assert mod.x == 2

    @skip_backends('C')
    def test_True_False(self):
        mod = self.compile("""
        def get_True() -> bool:
            return True

        def get_False() -> bool:
            return False
        """)
        assert mod.get_True() is True
        assert mod.get_False() is False


    @skip_backends('C')
    def test_CompareOp(self):
        mod = self.compile("""
        def cmp_eq (x: i32, y: i32) -> bool: return x == y
        def cmp_neq(x: i32, y: i32) -> bool: return x != y
        def cmp_lt (x: i32, y: i32) -> bool: return x  < y
        def cmp_lte(x: i32, y: i32) -> bool: return x <= y
        def cmp_gt (x: i32, y: i32) -> bool: return x  > y
        def cmp_gte(x: i32, y: i32) -> bool: return x >= y
        """)
        assert mod.cmp_eq(5, 5) is True
        assert mod.cmp_eq(5, 6) is False
        #
        assert mod.cmp_neq(5, 5) is False
        assert mod.cmp_neq(5, 6) is True
        #
        assert mod.cmp_lt(5, 6) is True
        assert mod.cmp_lt(5, 5) is False
        assert mod.cmp_lt(6, 5) is False
        #
        assert mod.cmp_lte(5, 6) is True
        assert mod.cmp_lte(5, 5) is True
        assert mod.cmp_lte(6, 5) is False
        #
        assert mod.cmp_gt(5, 6) is False
        assert mod.cmp_gt(5, 5) is False
        assert mod.cmp_gt(6, 5) is True
        #
        assert mod.cmp_gte(5, 6) is False
        assert mod.cmp_gte(5, 5) is True
        assert mod.cmp_gte(6, 5) is True

    @skip_backends('C')
    def test_CompareOp_error(self):
        self.expect_errors(
            f"""
            def foo(a: i32, b: str) -> bool:
                return a == b
            """,
            errors = [
                'cannot do `i32` == `str`',
                'this is `i32`',
                'this is `str`',
            ]
        )

    @skip_backends('C')
    def test_if(self):
        mod = self.compile("""
        a: i32 = 0
        b: i32 = 0
        c: i32 = 0

        def reset() -> void:
            a = 0
            b = 0
            c = 0

        def if_then(x: i32) -> void:
            if x == 0:
                a = 100
            c = 300

        def if_then_else(x: i32) -> void:
            if x == 0:
                a = 100
            else:
                b = 200
            c = 300

        """)
        #
        mod.if_then(0)
        assert mod.a == 100
        assert mod.c == 300
        #
        mod.reset()
        mod.if_then(1)
        assert mod.a == 0
        assert mod.c == 300
        #
        mod.reset()
        mod.if_then_else(0)
        assert mod.a == 100
        assert mod.b == 0
        assert mod.c == 300
        #
        mod.reset()
        mod.if_then_else(1)
        assert mod.a == 0
        assert mod.b == 200
        assert mod.c == 300

    @skip_backends('C')
    def test_while(self):
        mod = self.compile("""
        def factorial(n: i32) -> i32:
            res: i32 = 1
            i: i32 = 1
            while i <= n:
                res = res * i
                i = i + 1
            return res
        """)
        #
        assert mod.factorial(0) == 1
        assert mod.factorial(5) == 120

    @skip_backends('C')
    def test_if_while_errors(self):
        # XXX: eventually, we want to introduce the concept of "truth value"
        # and insert automatic conversions but for now the condition must be a
        # bool
        self.expect_errors(
            f"""
            def foo(a: i32) -> i32:
                if a:
                    return 1
                return 2
            """,
            errors = [
                'mismatched types',
                'expected `bool`, got `i32`',
                'implicit conversion to `bool` is not implemented yet'
            ]
        )
        #
        self.expect_errors(
            f"""
            def foo() -> void:
                while 1:
                    pass
            """,
            errors = [
                'mismatched types',
                'expected `bool`, got `i32`',
                'implicit conversion to `bool` is not implemented yet'
            ]
        )
