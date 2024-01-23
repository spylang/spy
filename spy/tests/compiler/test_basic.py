import pytest
from spy.fqn import FQN
from spy.errors import SPyTypeError
from spy.vm.builtins import B
from spy.tests.support import (CompilerTest, skip_backends, no_backend,
                               expect_errors, only_interp)

class TestBasic(CompilerTest):

    def test_simple(self):
        mod = self.compile(
        """
        def foo() -> i32:
            return 42
        """)
        assert mod.foo() == 42
        if self.backend == 'interp':
            assert not mod.foo.w_func.redshifted
        elif self.backend == 'doppler':
            assert mod.foo.w_func.redshifted

    def test_NameError(self):
        src = """
        def foo() -> i32:
            return x
        """
        errors = expect_errors(
            'name `x` is not defined',
            ('not found in this scope', 'x')
        )
        self.compile_raises(src, 'foo', errors)

    def test_resolve_type_errors(self):
        # NOTE: this error is always eager because it doesn't happen when
        # running the function, but when defining it
        src = """
        def foo() -> aaa:
            return 42
        """
        errors = expect_errors(
            'name `aaa` is not defined',
            ('not found in this scope', 'aaa')
        )
        self.compile_raises(src, 'foo', errors, error_reporting='eager')

    def test_wrong_functype_restype(self):
        src = """
        def foo() -> 'hello':
            return 42
        """
        errors = expect_errors(
            'expected `type`, got `str`',
            ('expected `type`', "'hello'")
        )
        self.compile_raises(src, 'foo', errors, error_reporting='eager')

    def test_wrong_functype_argtype(self):
        src = """
        def foo(x: 'hello') -> i32:
            return 42
        """
        errors = expect_errors(
            'expected `type`, got `str`',
            ('expected `type`', "'hello'"),
        )
        self.compile_raises(src, 'foo', errors, error_reporting='eager')

    def test_wrong_return_type(self):
        src = """
        def foo() -> str:
            return 42
        """
        errors = expect_errors(
            'mismatched types',
            ('expected `str`, got `i32`', "42"),
            ('expected `str` because of return type', "str"),
        )
        self.compile_raises(src, 'foo', errors)

    def test_local_variables(self):
        mod = self.compile(
        """
        def foo() -> i32:
            x: i32 = 42
            return x
        """)
        assert mod.foo() == 42

    def test_local_typecheck(self):
        src = """
        def foo() -> i32:
            x: str = 1
        """
        errors = expect_errors(
            'mismatched types',
            ('expected `str`, got `i32`', '1'),
            ('expected `str` because of type declaration', 'str'),
        )
        self.compile_raises(src, "foo", errors)

    @skip_backends('C', reason='type <object> not supported')
    def test_upcast_and_downcast(self):
        mod = self.compile("""
        def foo() -> i32:
            x: i32 = 1
            # this works, but it will check the type at runtime
            y: object = x
            return y
        """)
        assert mod.foo() == 1

    @skip_backends('C', reason='type <object> not supported')
    def test_downcast_error(self):
        # NOTE: we don't check this with expect_errors because this is ALWAYS
        # a runtime error. The compilation always succeed.
        mod = self.compile("""
        def foo() -> str:
            x: i32 = 1
            y: object = x
            return y
        """)
        msg = "Invalid cast. Expected `str`, got `i32`"
        with pytest.raises(SPyTypeError, match=msg):
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
            a = x + 1
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

    def test_global_variables(self):
        mod = self.compile(
        """
        var x: i32 = 42
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

    def test_cannot_assign_to_const_globals(self):
        src = """
        x: i32 = 42
        def set_x() -> void:
            x = 100
        """
        errors = expect_errors(
            'invalid assignment target',
            ('x is const', 'x'),
            ('const declared here', 'x: i32 = 42'),
            ('help: declare it as variable: `var x ...`', 'x: i32 = 42')
        )
        self.compile_raises(src, "set_x", errors)

    def test_i32_add(self):
        mod = self.compile("""
        def add(x: i32, y: i32) -> i32:
            return x + y
        """)
        assert mod.add(1, 2) == 3

    def test_i32_mul(self):
        mod = self.compile("""
        def mul(x: i32, y: i32) -> i32:
            return x * y
        """)
        assert mod.mul(3, 4) == 12

    def test_void_return(self):
        mod = self.compile("""
        var x: i32 = 0
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

    def test_implicit_return(self):
        mod = self.compile("""
        var x: i32 = 0
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
            # in the C backend we just abort without reporting an error, for now
            msg = 'reached the end of the function without a `return`'
            with pytest.raises(SPyTypeError, match=msg):
                mod.implicit_return_i32()

    def test_BinOp_error(self):
        src = """
        def bar(a: i32, b: str) -> void:
            return a + b

        def foo() -> void:
            bar(1, "hello")
        """
        errors = expect_errors(
            'cannot do `i32` + `str`',
            ('this is `i32`', 'a'),
            ('this is `str`', 'b'),
        )
        self.compile_raises(src, "foo", errors)

    def test_BinOp_is_dispatched_with_static_types(self):
        # this fails because the static type of 'x' is object, even if its
        # dynamic type is i32
        src = """
        def foo() -> i32:
            a: object = 1
            b: i32 = 2
            return a + b
        """
        errors = expect_errors(
            'cannot do `object` + `i32`',
            ('this is `object`', 'a'),
            ('this is `i32`', 'b'),
        )
        self.compile_raises(src, "foo", errors)

    def test_function_call(self):
        mod = self.compile("""
        def foo(x: i32, y: i32, z: i32) -> i32:
            return x*100 + y*10 + z

        def bar(y: i32) -> i32:
            return foo(y, y+1, y+2)
        """)
        assert mod.foo(1, 2, 3) == 123
        assert mod.bar(4) == 456

    def test_cannot_call_non_functions(self):
        # it would be nice to report also the location where 'inc' is defined,
        # but we don't carry around this information for now. There is room
        # for improvement
        src = """
        x: i32 = 0
        def foo() -> void:
            return x(0)
        """
        errors = expect_errors(
            'cannot call objects of type `i32`',
            ('this is not a function', 'x'),
            ('variable defined here', 'x: i32 = 0'),
        )
        self.compile_raises(src, "foo", errors)

    def test_function_call_missing_args(self):
        src = """
        def inc(x: i32) -> i32:
            return x+1
        def foo() -> void:
            return inc()
        """
        errors = expect_errors(
            'this function takes 1 argument but 0 arguments were supplied',
            ('1 argument missing', 'inc'),
            ('function defined here', 'def inc(x: i32) -> i32'),
        )
        self.compile_raises(src, "foo", errors)

    def test_function_call_extra_args(self):
        src = """
        def inc(x: i32) -> i32:
            return x+1
        def foo() -> void:
            return inc(1, 2, 3)
        """
        errors = expect_errors(
            'this function takes 1 argument but 3 arguments were supplied',
            ('2 extra arguments', '2, 3'),
            ('function defined here', 'def inc(x: i32) -> i32'),
        )
        self.compile_raises(src, 'foo', errors)

    def test_function_call_type_mismatch(self):
        src = """
        def inc(x: i32) -> i32:
            return x+1
        def foo() -> i32:
            return inc("hello")
        """
        errors = expect_errors(
            'mismatched types',
            ('expected `i32`, got `str`', '"hello"'),
            ('function defined here', 'def inc(x: i32) -> i32'),
        )
        self.compile_raises(src, "foo", errors)

    def test_StmtExpr(self):
        mod = self.compile("""
        var x: i32 = 0
        def inc() -> void:
            x = x + 1

        def foo() -> void:
            inc()
            inc()
        """)
        mod.foo()
        assert mod.x == 2

    def test_True_False(self):
        mod = self.compile("""
        def get_True() -> bool:
            return True

        def get_False() -> bool:
            return False
        """)
        assert mod.get_True() is True
        assert mod.get_False() is False

    def test_CompareOp(self):
        mod = self.compile("""
        def cmp_eq (x: i32, y: i32) -> bool: return x == y
        def cmp_neq(x: i32, y: i32) -> bool: return x != y
        ## def cmp_lt (x: i32, y: i32) -> bool: return x  < y
        ## def cmp_lte(x: i32, y: i32) -> bool: return x <= y
        ## def cmp_gt (x: i32, y: i32) -> bool: return x  > y
        ## def cmp_gte(x: i32, y: i32) -> bool: return x >= y
        """)
        assert mod.cmp_eq(5, 5) is True
        assert mod.cmp_eq(5, 6) is False
        #
        assert mod.cmp_neq(5, 5) is False
        assert mod.cmp_neq(5, 6) is True
        ## #
        ## assert mod.cmp_lt(5, 6) is True
        ## assert mod.cmp_lt(5, 5) is False
        ## assert mod.cmp_lt(6, 5) is False
        ## #
        ## assert mod.cmp_lte(5, 6) is True
        ## assert mod.cmp_lte(5, 5) is True
        ## assert mod.cmp_lte(6, 5) is False
        ## #
        ## assert mod.cmp_gt(5, 6) is False
        ## assert mod.cmp_gt(5, 5) is False
        ## assert mod.cmp_gt(6, 5) is True
        ## #
        ## assert mod.cmp_gte(5, 6) is False
        ## assert mod.cmp_gte(5, 5) is True
        ## assert mod.cmp_gte(6, 5) is True

    def test_CompareOp_error(self):
        src = """
        def bar(a: i32, b: str) -> bool:
            return a == b

        def foo() -> void:
            bar(1, "hello")
        """
        errors = expect_errors(
            'cannot do `i32` == `str`',
            ('this is `i32`', 'a'),
            ('this is `str`', 'b'),
        )
        self.compile_raises(src, 'foo', errors)

    def test_if_stmt(self):
        mod = self.compile("""
        var a: i32 = 0
        var b: i32 = 0
        var c: i32 = 0

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

    def test_if_error(self):
        # XXX: eventually, we want to introduce the concept of "truth value"
        # and insert automatic conversions but for now the condition must be a
        # bool
        src = """
        def bar(a: i32) -> i32:
            if a:
                return 1
            return 2

        def foo() -> void:
            bar(1)
        """
        errors = expect_errors(
            'mismatched types',
            ('expected `bool`, got `i32`', 'a'),
            ('implicit conversion to `bool` is not implemented yet', 'a')
        )
        self.compile_raises(src, "foo", errors)

    def test_while_error(self):
        src = """
        def foo() -> void:
            while 123:
                pass
        """
        errors = expect_errors(
            'mismatched types',
            ('expected `bool`, got `i32`', '123'),
            ('implicit conversion to `bool` is not implemented yet', '123')
        )
        self.compile_raises(src, "foo", errors)

    def test_getitem_error_1(self):
        src = """
        def bar(a: str, i: bool) -> void:
            a[i]

        def foo() -> void:
            bar("hello", True)
        """
        errors = expect_errors(
            'cannot do `str`[`bool`]',
            ('this is `str`', 'a'),
            ('this is `bool`', 'i'),
            )
        self.compile_raises(src, "foo", errors)

    def test_builtin_function(self):
        mod = self.compile("""
        def foo(x: i32) -> i32:
            return abs(x)
        """)
        #
        assert mod.foo(10) == 10
        assert mod.foo(-20) == 20

    def test_resolve_name(self):
        mod = self.compile("""
        from builtins import i32 as my_int

        def foo(x: my_int) -> my_int:
            return x+1
        """)
        #
        w_functype = mod.foo.w_functype
        assert w_functype.name == 'def(x: i32) -> i32'
        assert mod.foo(1) == 2
