import pytest
from spy.fqn import FQN
from spy.errors import SPyRuntimeAbort
from spy.vm.vm import Builtins as B
from spy.tests.support import (CompilerTest, skip_backends, no_backend,
                               expect_errors)

class TestBasic(CompilerTest):

    def test_simple(self):
        mod = self.compile(
        """
        def foo() -> i32:
            return 42
        """)
        assert mod.foo() == 42

    def test_NameError(self):
        ctx = expect_errors(
            'name `x` is not defined',
            ('not found in this scope', 'x')
        )
        with ctx:
            mod = self.compile(
            """
            def foo() -> i32:
                return x
            """)
            mod.foo()

    def test_resolve_type_errors(self):
        ctx = expect_errors(
            'name `aaa` is not defined',
            ('not found in this scope', 'aaa')
        )
        with ctx:
            mod = self.compile("""
            def foo() -> aaa:
                return 42
            """)

    def test_wrong_functype_restype(self):
        ctx = expect_errors(
            'expected `type`, got `str`',
            ('expected `type`', "'hello'")
        )
        with ctx:
            self.compile("""
            def foo() -> 'hello':
                return 42
            """)

    def test_wrong_functype_argtype(self):
        ctx = expect_errors(
            'expected `type`, got `str`',
            ('expected `type`', "'hello'"),
        )
        with ctx:
            self.compile("""
            def foo(x: 'hello') -> i32:
                return 42
            """)

    def test_wrong_return_type(self):
        ctx = expect_errors(
            'mismatched types',
            ('expected `str`, got `i32`', "return 42"),
            ('expected `str` because of return type', "str"),
        )
        with ctx:
            mod = self.compile("""
            def foo() -> str:
                return 42
            """)
            mod.foo()

    def test_local_variables(self):
        mod = self.compile(
        """
        def foo() -> i32:
            x: i32 = 42
            return x
        """)
        assert mod.foo() == 42

    def test_local_typecheck(self):
        ctx = expect_errors(
            'mismatched types',
            ('expected `str`, got `i32`', '1'),
            ('expected `str` because of type declaration', 'str'),
        )
        with ctx:
            mod = self.compile("""
            def foo() -> i32:
                x: str = 1
            """)
            mod.foo()

    def test_function_arguments(self):
        mod = self.compile(
        """
        def inc(x: i32) -> i32:
            return x + 1
        """)
        assert mod.inc(100) == 101

    def test_assign(self):
        mod = self.compile(
        """
        def inc(x: i32) -> i32:
            a: i32 = 0
            b = 1 # implicit declaration
            a = x + b
            return a
        """)
        assert mod.inc(100) == 101

    def test_implicit_declaration(self):
        mod = self.compile(
            """
            def foo() -> i32:
                x = 42
                return x
            """)
        assert mod.foo() == 42

    def test_global_variables(self, legacy):
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

    def test_i32_add(self, legacy):
        mod = self.compile("""
        def add(x: i32, y: i32) -> i32:
            return x + y
        """)
        assert mod.add(1, 2) == 3

    def test_i32_mul(self, legacy):
        mod = self.compile("""
        def mul(x: i32, y: i32) -> i32:
            return x * y
        """)
        assert mod.mul(3, 4) == 12

    def test_void_return(self, legacy):
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

    def test_implicit_return(self, legacy):
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

        if self.backend != 'C':
            # we don't support the opcode abort() in the C backend for now
            msg = 'reached the end of the function without a `return`'
            with pytest.raises(SPyRuntimeAbort, match=msg):
                mod.implicit_return_i32()


    @no_backend
    def test_BinOp_error(self, legacy):
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

    def test_function_call(self, legacy):
        mod = self.compile("""
        def foo(x: i32, y: i32, z: i32) -> i32:
            return x*100 + y*10 + z

        def bar(y: i32) -> i32:
            return foo(y, y+1, y+2)
        """)
        assert mod.foo(1, 2, 3) == 123
        assert mod.bar(4) == 456

    @no_backend
    def test_function_call_errors(self, legacy):
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

    def test_StmtExpr(self, legacy):
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

    def test_True_False(self, legacy):
        mod = self.compile("""
        def get_True() -> bool:
            return True

        def get_False() -> bool:
            return False
        """)
        assert mod.get_True() is True
        assert mod.get_False() is False

    def test_CompareOp(self, legacy):
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

    @no_backend
    def test_CompareOp_error(self, legacy):
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

    def test_if_stmt(self, legacy):
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

    def test_while(self, legacy):
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

    @no_backend
    def test_if_while_errors(self, legacy):
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

    @pytest.mark.xfail(reason='FIXME')
    @no_backend
    def test_getitem_errors(self, legacy):
        self.expect_errors(
            f"""
            def foo(a: str, i: bool) -> void:
                a[i]
            """,
            errors = [
                'mismatched types',
                'expected `i32`, got `bool`',
                'this is a `str`',
            ]
        )
        #
        self.expect_errors(
            f"""
            def foo(a: bool, i: i32) -> void:
                a[i]
            """,
            errors = [
                '`bool` does not support `[]`',
                'this is a `bool`',
            ]
        )

    def test_builtin_function(self, legacy):
        mod = self.compile("""
        def foo(x: i32) -> i32:
            return abs(x)
        """)
        #
        assert mod.foo(10) == 10
        assert mod.foo(-20) == 20

    def test_resolve_name(self, legacy):
        mod = self.compile("""
        from builtins import i32 as my_int

        def foo(x: my_int) -> my_int:
            return x+1
        """)
        #
        w_functype = mod.foo.w_functype
        assert w_functype.name == 'def(x: i32) -> i32'
        assert mod.foo(1) == 2
