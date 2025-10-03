import pytest
from spy.fqn import FQN
from spy.errors import SPyError
from spy.vm.b import B
from spy.fqn import FQN
from spy.tests.support import (CompilerTest, skip_backends, expect_errors, only_interp, no_C)

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

    def test_return_None(self):
        mod = self.compile(
        """
        def foo() -> None:
            pass
        """)
        assert mod.foo() is None

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

    @only_interp
    def test_blue_cannot_redeclare(self):
        # see also the equivalent test
        # TestScopeAnalyzer.test_red_cannot_redeclare
        src = """
        @blue
        def foo() -> i32:
            x: i32 = 1
            x: i32 = 2
        """
        errors = expect_errors(
            'variable `x` already declared',
            ('this is the new declaration', "x: i32 = 2"),
            ('this is the previous declaration', "x: i32 = 1"),
        )
        self.compile_raises(src, "foo", errors)

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
        with SPyError.raises('W_TypeError', match=msg):
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
        def set_x(newval: i32) -> None:
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
        def set_x() -> None:
            x = 100
        """
        errors = expect_errors(
            'invalid assignment target',
            ('x is const', 'x'),
            ('const declared here', 'x: i32 = 42'),
            ('help: declare it as variable: `var x ...`', 'x: i32 = 42')
        )
        self.compile_raises(src, "set_x", errors)

    @only_interp
    def test_int_float(self):
        mod = self.compile("""
        def try_int() -> bool:
            return int == i32

        def try_float() -> bool:
            return float == f64
        """)
        assert mod.try_int()
        assert mod.try_float()

    def test_void_return(self):
        mod = self.compile("""
        var x: i32 = 0
        def foo() -> None:
            x = 1
            return
            x = 2

        def bar() -> None:
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
        def implicit_return_void() -> None:
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
            with SPyError.raises('W_TypeError', match=msg):
                mod.implicit_return_i32()

    def test_BinOp_error(self):
        src = """
        def bar(a: i32, b: str) -> None:
            return a + b

        def foo() -> None:
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

    def test_conversions(self):
        mod = self.compile(
        """
        def a(x: i32) -> f64:
            return x

        def b(x: i32) -> bool:
            return x
        """)
        res = mod.a(1)
        assert res == 1.0 and type(res) is float
        assert mod.b(1) is True

    def test_cannot_call_non_functions(self):
        # it would be nice to report also the location where 'inc' is defined,
        # but we don't carry around this information for now. There is room
        # for improvement
        src = """
        x: i32 = 0
        def foo() -> None:
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
        def foo() -> None:
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
        def foo() -> None:
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
        def inc() -> None:
            x = x + 1

        def foo() -> None:
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

    def test_bool_equality(self):
        mod = self.compile("""
        def eq_bool(a: bool, b: bool) -> bool:
            return a == b

        def ne_bool(a: bool, b: bool) -> bool:
            return a != b
        """)
        assert mod.eq_bool(True, True) is True
        assert mod.eq_bool(True, False) is False
        assert mod.eq_bool(False, True) is False
        assert mod.eq_bool(False, False) is True

        assert mod.ne_bool(True, True) is False
        assert mod.ne_bool(True, False) is True
        assert mod.ne_bool(False, True) is True
        assert mod.ne_bool(False, False) is False

    def test_bool_operations(self):
        mod = self.compile("""
        def and_bool(a: bool, b: bool) -> bool:
            return a & b

        def or_bool(a: bool, b: bool) -> bool:
            return a | b

        def xor_bool(a: bool, b: bool) -> bool:
            return a ^ b

        def lt_bool(a: bool, b: bool) -> bool:
            return a < b

        def le_bool(a: bool, b: bool) -> bool:
            return a <= b

        def gt_bool(a: bool, b: bool) -> bool:
            return a > b

        def ge_bool(a: bool, b: bool) -> bool:
            return a >= b
        """)

        # Test AND
        assert mod.and_bool(True, True) is True
        assert mod.and_bool(True, False) is False
        assert mod.and_bool(False, True) is False
        assert mod.and_bool(False, False) is False

        # Test OR
        assert mod.or_bool(True, True) is True
        assert mod.or_bool(True, False) is True
        assert mod.or_bool(False, True) is True
        assert mod.or_bool(False, False) is False

        # Test XOR
        assert mod.xor_bool(True, True) is False
        assert mod.xor_bool(True, False) is True
        assert mod.xor_bool(False, True) is True
        assert mod.xor_bool(False, False) is False

        # Test <
        assert mod.lt_bool(True, True) is False
        assert mod.lt_bool(True, False) is False
        assert mod.lt_bool(False, True) is True
        assert mod.lt_bool(False, False) is False

        # Test <=
        assert mod.le_bool(True, True) is True
        assert mod.le_bool(True, False) is False
        assert mod.le_bool(False, True) is True
        assert mod.le_bool(False, False) is True

        # Test >
        assert mod.gt_bool(True, True) is False
        assert mod.gt_bool(True, False) is True
        assert mod.gt_bool(False, True) is False
        assert mod.gt_bool(False, False) is False

        # Test >=
        assert mod.ge_bool(True, True) is True
        assert mod.ge_bool(True, False) is True
        assert mod.ge_bool(False, True) is False
        assert mod.ge_bool(False, False) is True

    def test_CompareOp_error(self):
        src = """
        def bar(a: i32, b: str) -> bool:
            return a == b

        def foo() -> None:
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

        def reset() -> None:
            a = 0
            b = 0
            c = 0

        def if_then(x: i32) -> None:
            if x == 0:
                a = 100
            c = 300

        def if_then_else(x: i32) -> None:
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
        def foo() -> None:
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
        def bar(a: i32, i: bool) -> None:
            a[i]

        def foo() -> None:
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

    def test_max_min(self):
        mod = self.compile("""
        def mymax(x: i32, y: i32) -> i32: return max(x, y)
        def mymin(x: i32, y: i32) -> i32: return min(x, y)
        """)
        #
        assert mod.mymax(10, 20) == 20
        assert mod.mymax(20, 10) == 20
        assert mod.mymax(-5, 5) == 5

        assert mod.mymin(10, 20) == 10
        assert mod.mymin(20, 10) == 10
        assert mod.mymin(-5, 5) == -5

    def test_aug_assign(self):
        mod = self.compile("""
        def foo(x: i32) -> i32:
            x += 1
            x *= 2
            x -= 3
            return x
        """)
        assert mod.foo(10) == ((10 + 1) * 2) - 3

    def test_resolve_name(self):
        mod = self.compile("""
        from builtins import i32 as my_int

        def foo(x: my_int) -> my_int:
            return x+1
        """)
        #
        w_functype = mod.foo.w_functype
        assert w_functype.fqn.human_name == 'def(i32) -> i32'
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
        assert mod.foo() == 9

    def test_blue_generic(self):
        mod = self.compile("""
        @blue.generic
        def add(T):
            def impl(x: T, y: T) -> T:
                return x + y
            return impl

        def foo() -> i32:
            return add[i32](1, 2)

        def bar() -> str:
            return add[str]('hello ', 'world')
        """)
        assert mod.foo() == 3
        assert mod.bar() == 'hello world'

    def test_cannot_call_blue_generic(self):
        src = """
        @blue.generic
        def ident(x):
            return x

        def foo() -> i32:
            return ident(42)
        """
        errors = expect_errors(
            'generic functions must be called via `[...]`',
            ('this is `@blue.generic def(dynamic) -> dynamic`', 'ident'),
            ("`ident` defined here", "def ident(x):")
            )
        self.compile_raises(src, "foo", errors)

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
        def foo() -> None:
            print("hello world")
            print(42)
            print(12.3)
            print(True)
            print(None)
            print(i32)
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
                                 "<spy type 'i32'>",
                                 ""])

    @no_C
    def test_print_object(self, capfd):
        mod = self.compile("""
        def foo() -> None:
            x = i32   # force i32 to be a red value
            print(x)
        """)
        mod.foo()
        out, err = capfd.readouterr()
        assert out == "<spy type 'i32'>\n"

    def test_deeply_nested_closure(self, capfd):
        mod = self.compile("""
        x0 = 0

        @blue
        def a():
            x1 = 1
            @blue
            def b():
                x2 = 2
                def c() -> None:
                    x3 = 3
                    print(x0)
                    print(x1)
                    print(x2)
                    print(x3)
                return c
            return b

        def foo() -> None:
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

        def get_x() -> i32:
            return x
        """)
        vm = self.vm
        assert mod.get_x() == 7
        if self.backend != 'C':
            w_mod = self.vm.modules_w['test']
            w_x = w_mod.getattr('x')
            assert vm.unwrap(w_x) == 7

    def test_getattr_module(self):
        mod = self.compile("""
        import builtins

        def foo() -> builtins.i32:
            return 42
        """)
        assert mod.foo() == 42

    def test_getattr_error(self):
        src = """
        def foo() -> None:
            x: object = 1
            x.foo
        """
        errors = expect_errors(
            "type `object` has no attribute 'foo'",
            ('this is `object`', 'x'),
            )
        self.compile_raises(src, "foo", errors)

    @pytest.mark.skip(reason="think better about __INIT__")
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
        assert mod.get_x() == 42
        fqn = FQN("test::x")
        assert vm.unwrap(self.vm.globals_w[fqn]) == 42

    @pytest.mark.skip(reason="think better about __INIT__")
    def test_wrong__INIT__(self):
        # NOTE: this error is always eager because it happens at import time
        src = """
        def __INIT__(mod: dynamic) -> None:
            pass
        """
        errors = expect_errors(
            "the __INIT__ function must be @blue",
            ("function defined here", "def __INIT__(mod: dynamic) -> None")
        )
        self.compile_raises(src, "", errors, error_reporting="eager")

    def test_setattr_error(self):
        src = """
        def foo() -> None:
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

    def test_str2f64(self):
        mod = self.compile("""
        def foo(x: f64) -> str:
            return str(x)
        """)
        #
        assert mod.foo(0.0) == '0'
        assert mod.foo(3.14) == '3.14'
        assert mod.foo(123.456) == '123.456'

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
        with SPyError.raises('W_TypeError', match=msg):
            mod.eq_wrong_types(1, 'hello')
        #
        msg = "cannot do `object` == `object`"
        with SPyError.raises('W_TypeError', match=msg):
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

    @only_interp
    def test_automatic_forward_declaration(self):
        mod = self.compile("""
        from unsafe import ptr

        # we can use S even if it's declared later
        def foo(s: S, p: ptr[S]) -> None:
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
        expected_sig = 'def(test::S, unsafe::ptr[test::S]) -> None'
        assert w_foo.w_functype.fqn.human_name == expected_sig
        params = w_foo.w_functype.params
        assert params[0].w_T is w_S
        assert params[1].w_T is w_ptr_S1 is w_ptr_S2

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
        w_T = mod.foo(unwrap=False)
        assert w_T is B.w_i32

    def test_cls_as_param_name(self):
        mod = self.compile("""
        def foo(cls: i32) -> i32:
            return cls+1
        """)
        assert mod.foo(3) == 4

    def test_call_module_attr(self):
        mod = self.compile("""
        import math

        def foo(x: f64) -> f64:
            return math.fabs(x)
        """)
        assert mod.foo(-3.5) == 3.5

    def test_cannot_call_red_from_blue(self):
        src = """
        @blue
        def blue_inc(x):
            return x + 1

        def foo() -> i32:
            x = 2
            return blue_inc(x)
        """
        errors = expect_errors(
            'cannot call blue function with red arguments',
            ('this is blue', 'blue_inc'),
            ('this is red', 'x'),
        )
        self.compile_raises(src, 'foo', errors)

    def test_varargs_blue(self):
        src = """
        @blue
        def foo(a, b, *args):
            return len(args)

        def bar() -> i32:
            return foo(1, 2, 3, 4, 5)
        """
        mod = self.compile(src)
        assert mod.bar() == 3

    def test_varargs_red(self):
        src = """
        def foo(a: i32, b: i32, *args: i32) -> i32:
            return len(args)

        def bar() -> i32:
            return foo(1, 2, 3, 4, 5)
        """
        if self.backend == 'C':
            errors = expect_errors(
                '*args not yet supported by the C backend',
                ('*args declared here', 'args: i32')
            )
            self.compile_raises(src, "foo", errors)
        else:
            mod = self.compile(src)
            assert mod.bar() == 3

    def test_call_functions_during_redshifting(self):
        # this test what happens in the middle of redshifting. When we are
        # redshifting get_N(), "inc" has already been redshifted but get_N
        # tries to call the old function object. ASTFrame has a special check
        # to automatically use the new version instead.
        src = """
        def inc(x: i32) -> i32:
            return x + 1

        @blue
        def get_N():
            return inc(5)

        def foo() -> i32:
            return get_N()
        """
        mod = self.compile(src)
        assert mod.foo() == 6

    def test_decorator(self):
        src = """
        @blue
        def double(fn):
            def inner(x: i32) -> i32:
                res = fn(x)
                return res * 2
            return inner

        @double
        def inc(x: i32) -> i32:
            return x + 1

        def foo(x: i32) -> i32:
            return inc(x)
        """
        mod = self.compile(src)
        assert mod.foo(5) == 12

    def test_multiple_decorator(self):
        src = """
        @blue
        def inc(fn):
            def inner(x: i32) -> i32:
                return fn(x) + 1
            return inner

        @blue
        def double(fn):
            def inner(x: i32) -> i32:
                return fn(x) * 2
            return inner

        @inc
        @double
        def x2_plus_1(x: i32) -> i32:
            return x
        """
        mod = self.compile(src)
        assert mod.x2_plus_1(5) == 11

    def test_for_loop(self):
        src = """
        from _range import range

        def factorial(n: i32) -> i32:
            res = 1
            for i in range(n):
                res *= (i+1)
            return res
        """
        mod = self.compile(src)
        assert mod.factorial(4) == 2 * 3 * 4

    def test_break_in_while(self):
        src = """
        def foo() -> i32:
            i = 0
            while i < 10:
                if i == 5:
                    break
                i += 1
            return i
        """
        mod = self.compile(src)
        assert mod.foo() == 5

    def test_continue_in_while(self):
        src = """
        def foo() -> i32:
            i = 0
            count = 0
            while i < 10:
                i += 1
                if i % 2 == 0:
                    continue
                count += 1
            return count
        """
        mod = self.compile(src)
        assert mod.foo() == 5  # counts odd numbers from 1 to 9

    def test_break_in_for(self):
        src = """
        from _range import range

        def foo() -> i32:
            total = 0
            for i in range(10):
                if i == 5:
                    break
                total += i
            return total
        """
        mod = self.compile(src)
        assert mod.foo() == 0 + 1 + 2 + 3 + 4

    def test_continue_in_for(self):
        src = """
        from _range import range

        def foo() -> i32:
            total = 0
            for i in range(10):
                if i % 2 == 0:
                    continue
                total += i
            return total
        """
        mod = self.compile(src)
        assert mod.foo() == 1 + 3 + 5 + 7 + 9

    def test_nested_loops_with_break(self):
        src = """
        from _range import range

        def foo() -> i32:
            total = 0
            for i in range(5):
                for j in range(5):
                    if j == 3:
                        break
                    total += 1
            return total
        """
        mod = self.compile(src)
        assert mod.foo() == 5 * 3  # 5 outer iterations, 3 inner iterations each
