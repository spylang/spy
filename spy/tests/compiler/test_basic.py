import pytest
from spy.fqn import FQN
from spy.errors import SPyTypeError
from spy.vm.b import B
from spy.fqn import FQN
from spy.tests.support import (CompilerTest, skip_backends, no_backend,
                               expect_errors, only_interp, no_C)

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

    def test_binop(self):
        mod = self.compile(
        """
        def foo() -> i32:
            return 1 + 2
        """)
        assert mod.foo() == 3

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

    def test_i32_BinOp(self):
        mod = self.compile("""
        def add(x: i32, y: i32) -> i32: return x + y
        def sub(x: i32, y: i32) -> i32: return x - y
        def mul(x: i32, y: i32) -> i32: return x * y
        def div(x: i32, y: i32) -> i32: return x / y
        def mod(x: i32, y: i32) -> i32: return x % y

        # XXX: should i32/i32 return an i32 or a float? For now we just do an
        # integer division
        """)
        assert mod.add(1, 2) == 3
        assert mod.sub(3, 4) == -1
        assert mod.mul(5, 6) == 30
        assert mod.div(10, 3) == 3
        assert mod.mod(10, 3) == 1

    def test_i32_BitwiseOp(self):
        mod = self.compile("""
        def shl(x: i32, y: i32) -> i32: return x << y
        def shr(x: i32, y: i32) -> i32: return x >> y
        def b_and(x: i32, y: i32) -> i32: return x & y
        def b_or(x: i32, y: i32) -> i32: return x | y
        def b_xor(x: i32, y: i32) -> i32: return x ^ y
        """)
        assert mod.shl(128, 4) == 128 << 4
        assert mod.shr(128, 4) == 128 >> 4
        assert mod.b_and(7, 3) == 7 & 3
        assert mod.b_and(127, 7) == 127 & 7
        assert mod.b_or(127, 123) == 127 | 123
        assert mod.b_or(127, 0) == 127 | 0
        assert mod.b_xor(16, 15) == 16 ^ 15
        assert mod.b_xor(16, 0) == 16 ^ 0

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

    @pytest.mark.skip(reason="the result of op.ADD should be blue but it's red")
    def test_explicit_BinOp(self):
        mod = self.compile("""
        import operator as op

        def foo(x: i32, y: i32) -> i32:
            return op.ADD(i32, i32)(x, y)
        """)
        assert mod.foo(3, 5) == 8


    def test_function_call(self):
        mod = self.compile("""
        def foo(x: i32, y: i32, z: i32) -> i32:
            return x*100 + y*10 + z

        def bar(y: i32) -> i32:
            return foo(y, y+1, y+2)
        """)
        assert mod.foo(1, 2, 3) == 123
        assert mod.bar(4) == 456

    def test_function_call_conversion(self):
        mod = self.compile(
        """
        def foo(x: f64) -> f64:
            return x / 2

        def bar(x: i32) -> f64:
            return foo(x)
        """)
        assert mod.bar(3) == 1.5

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
            ('this is `i32`', 'x'),
            ('`x` defined here', 'x: i32 = 0'),
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

    def test_pass(self):
        mod = self.compile("""
        def foo() -> void:
            pass
        """)
        assert mod.foo() is None

    def test_bool_conversion(self):
        mod = self.compile("""
        def foo(a: i32) -> i32:
            if a:
                return 100
            return 200
        """)
        assert mod.foo(1) == 100
        assert mod.foo(0) == 200

    def test_getitem_error_1(self):
        src = """
        def bar(a: i32, i: bool) -> void:
            a[i]

        def foo() -> void:
            bar(42, True)
        """
        errors = expect_errors(
            'cannot do `i32`[...]',
            ('this is `i32`', 'a'),
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
        assert w_functype.signature == 'def(x: i32) -> i32'
        assert mod.foo(1) == 2

    def test_redshift_nonglobal_function(self):
        mod = self.compile("""
        @blue
        def make_inc():
            def inc(x: i32) -> i32:
                return x + 1
            return inc

        def foo() -> i32:
            return make_inc()(6)
        """)
        assert mod.foo() == 7

    def test_call_blue_closure(self):
        mod = self.compile("""
        @blue
        def make_adder(x: i32):
            def adder(y: i32) -> i32:
                return x + y
            return adder

        def foo() -> i32:
            return make_adder(3)(6)
        """)
        mod.foo()

    def test_call_func_already_redshifted(self):
        mod = self.compile("""
        @blue
        def make_foo():
            def inc(x: i32) -> i32:
                return x + 1

            def foo(x: i32, y: i32) -> i32:
                return inc(x) * inc(y)
            return foo

        def bar() -> i32:
            return make_foo()(3, 4)
        """)
        assert mod.bar() == 20

    def test_print(self, capfd):
        mod = self.compile("""
        def foo() -> void:
            print("hello world")
            print(42)
            print(12.3)
            print(True)
            print(None)
        """)
        mod.foo()
        if self.backend == 'C':
            # NOTE: float formatting is done by printf and it's different than
            # the one that we get by Python in interp-mode. Too bad for now.
            s_123 = "12.300000"
            mod.ll.call('spy_flush')
        else:
            s_123 = "12.3"
        out, err = capfd.readouterr()
        assert out == '\n'.join(["hello world",
                                 "42",
                                 s_123,
                                 "True",
                                 "None",
                                 ""])

    def test_deeply_nested_closure(self, capfd):
        mod = self.compile("""
        x0 = 0

        @blue
        def a():
            x1 = 1
            @blue
            def b():
                x2 = 2
                def c() -> void:
                    x3 = 3
                    print(x0)
                    print(x1)
                    print(x2)
                    print(x3)
                return c
            return b

        def foo() -> void:
            a()()()
        """)
        mod.foo()
        if self.backend == 'C':
            mod.ll.call('spy_flush')
        out, err = capfd.readouterr()
        assert out.split() == ['0', '1', '2', '3']

    def test_capture_across_multiple_scopes(self):
        # see also the similar test in test_scope.py
        mod = self.compile("""
        @blue
        def a():
            x = 42  # x is defined in this scope
            @blue
            def b():
                # x is referenced but NOT defined in this scope
                y = x
                def c() -> i32:
                    # x should point TWO levels up
                    return x
                return c
            return b

        def foo() -> i32:
            return a()()()
        """)
        assert mod.foo() == 42

    def test_global_const_type_inference(self):
        mod = self.compile(
        """
        @blue
        def INIT_X():
            return 1 + 2 * 3

        x = INIT_X()
        """)
        vm = self.vm
        assert mod.x == 7
        fqn = FQN("test::x")
        assert vm.unwrap(self.vm.globals_w[fqn]) == 7

    def test_getattr_module(self):
        mod = self.compile("""
        import builtins

        def foo() -> builtins.i32:
            return 42
        """)
        assert mod.foo() == 42

    def test_getattr_error(self):
        src = """
        def foo() -> void:
            x: object = 1
            x.foo
        """
        errors = expect_errors(
            "type `object` has no attribute 'foo'",
            ('this is `object`', 'x'),
            )
        self.compile_raises(src, "foo", errors)

    def test___INIT__(self):
        mod = self.compile(
        """
        x: i32 = 0

        def get_x() -> i32:
            return x

        @blue
        def __INIT__(mod):
            mod.x = 42
        """)
        vm = self.vm
        assert mod.x == 42
        assert mod.get_x() == 42

    def test_wrong__INIT__(self):
        # NOTE: this error is always eager because it happens at import time
        src = """
        def __INIT__(mod: dynamic) -> void:
            pass
        """
        errors = expect_errors(
            "the __INIT__ function must be @blue",
            ("function defined here", "def __INIT__(mod: dynamic) -> void")
        )
        self.compile_raises(src, "", errors, error_reporting="eager")

    def test_setattr_error(self):
        src = """
        def foo() -> void:
            s: str = "hello"
            s.x = 42

        """
        errors = expect_errors(
            "type `str` does not support assignment to attribute 'x'",
            ("this is `str`", 's'),
        )
        self.compile_raises(src, "foo", errors)

    @no_C
    def test_blue_is_memoized(self, capsys):
        mod = self.compile("""
        @blue
        def foo(x: i32) -> i32:
            print(x)
            return x
        """)
        assert mod.foo(1) == 1
        assert mod.foo(1) == 1 # this should be cached
        assert mod.foo(2) == 2

        out, err = capsys.readouterr()
        assert out == '1\n2\n'

    def test_str2i32(self):
        mod = self.compile("""
        def foo(x: i32) -> str:
            return str(x)
        """)
        #
        assert mod.foo(0) == '0'
        assert mod.foo(9) == '9'
        assert mod.foo(123) == '123'

    @no_C
    def test_eq_reference_types(self):
        mod = self.compile("""
        @blue
        def type_eq(x: type, y: type) -> bool:
            return x == y

        @blue
        def type_ne(x: type, y: type) -> bool:
            return x != y
        """)
        assert mod.type_eq(B.w_i32, B.w_i32) == True
        assert mod.type_eq(B.w_i32, B.w_str) == False
        assert mod.type_ne(B.w_i32, B.w_i32) == False
        assert mod.type_ne(B.w_i32, B.w_str) == True

    @skip_backends('doppler', 'C', reason='we need lazy errors')
    def test_equality(self):
        mod = self.compile("""
        def eq_with_conversion(x: i32, y: f64) -> bool:
            return x == y

        def eq_wrong_types(x: i32, y: str) -> bool:
            return x == y

        def eq_objects(x: object, y: object) -> bool:
            return x == y

        def eq_dynamic(x: dynamic, y: dynamic) -> bool:
            return x == y

        def ne_dynamic(x: dynamic, y: dynamic) -> bool:
            return x != y

        """)
        assert mod.eq_with_conversion(1, 1.0) == True
        assert mod.eq_with_conversion(1, 2.0) == False
        #
        msg = "cannot do `i32` == `str`"
        with pytest.raises(SPyTypeError, match=msg):
            mod.eq_wrong_types(1, 'hello')
        #
        msg = "cannot do `object` == `object`"
        with pytest.raises(SPyTypeError, match=msg):
            mod.eq_objects(1, 2)
        #
        # `dynamic` == `dynamic` uses universal equality, so comparison
        # between different types is permitted
        assert mod.eq_dynamic(1, 1) == True
        assert mod.eq_dynamic(1, 2) == False
        assert mod.eq_dynamic(1, 'str') == False
        assert mod.ne_dynamic(1, 1) == False
        assert mod.ne_dynamic(1, 2) == True
        assert mod.ne_dynamic(1, 'str') == True

    @no_C
    def test_STATIC_TYPE(self):
        mod = self.compile("""
        def foo() -> type:
            x = 42
            return STATIC_TYPE(x)
        """)
        w_type = mod.foo(unwrap=False)
        assert w_type is B.w_i32

    @no_C
    def test_STATIC_TYPE_wrong_argcount(self):
        src = """
        def foo() -> type:
            x = 42
            return STATIC_TYPE(x, 1, 2)
        """
        errors = expect_errors(
            'this function takes 1 argument but 3 arguments were supplied',
            ('2 extra arguments', '1, 2')
        )
        self.compile_raises(src, 'foo', errors)

    @no_C
    def test_STATIC_TYPE_side_effects(self):
        # Ideally, we sould like to allow STATIC_TYPE on arbitrary
        # expressions: this is easy to implement for interp, but tricky for
        # doppler. For now, we declare that we support only simple expressions
        # as argument of STATIC_TYPE, to avoid side effects
        src = """
        var x: i32 = 0

        def get_x() -> i32:
            return x

        def inc() -> i32:
            x = x + 1
            return x

        def foo() -> type:
            return STATIC_TYPE(inc())
        """
        # this is what we would like, eventually
        ## assert mod.get_x() == 0
        ## pyclass = mod.foo()
        ## assert pyclass is self.vm.unwrap(B.w_i32)
        ## assert mod.get_x() == 1
        #
        # this is what we have now
        errors = expect_errors(
            'STATIC_TYPE works only on simple expressions',
            ('Call not allowed here', 'inc()')
        )
        self.compile_raises(src, 'foo', errors)

    @only_interp
    def test_automatic_forward_declaration(self):
        mod = self.compile("""
        from unsafe import ptr

        # we can use S even if it's declared later
        def foo(s: S, p: ptr[S]) -> void:
            pass

        ptr_S1 = ptr[S] # using the forward decl

        @struct
        class S:
            pass

        ptr_S2 = ptr[S] # using the actual S
        """)
        w_mod = mod.w_mod
        w_foo = w_mod.getattr('foo')
        w_S = w_mod.getattr('S')
        w_ptr_S1 = w_mod.getattr('ptr_S1')
        w_ptr_S2 = w_mod.getattr('ptr_S2')
        #
        expected_sig = 'def(s: test::S, p: unsafe::ptr[test::S]) -> void'
        assert w_foo.w_functype.signature == expected_sig
        params = w_foo.w_functype.params
        assert params[0].w_type is w_S
        assert params[1].w_type is w_ptr_S1 is w_ptr_S2

    @only_interp
    def test_forward_declaration_in_funcdef(self):
        mod = self.compile("""
        from unsafe import ptr, gc_alloc

        @blue
        def foo() -> i32:
            p: ptr[S]  # S is forward-declared at this point

            @struct
            class S:
                x: i32

            p = gc_alloc(S)(1)
            p.x = 42
            return p.x
        """)
        assert mod.foo() == 42

    @only_interp
    def test_eager_blue_eval(self):
        mod = self.compile("""
        @blue
        def bar() -> dynamic:
            return 42

        def foo() -> type:
            x = bar()
            return STATIC_TYPE(x)
        """)
        w_type = mod.foo(unwrap=False)
        assert w_type is B.w_i32

    def test_cls_as_param_name(self):
        mod = self.compile("""
        def foo(cls: i32) -> i32:
            return cls+1
        """)
        assert mod.foo(3) == 4
