import pytest

from spy.tests.support import (
    CompilerTest,
    expect_errors,
    only_interp,
    skip_backends,
)


class TestForceInline(CompilerTest):
    def test_simple_tail_return(self):
        mod = self.compile("""
        from __spy__ import force_inline

        @force_inline
        def add1(x: i32) -> i32:
            return x + 1

        def foo(x: i32) -> i32:
            return add1(x) + add1(x)
        """)
        assert mod.foo(10) == 22

    @only_interp
    def test_decorator(self):
        mod = self.compile("""
        from __spy__ import force_inline

        @force_inline
        def inc(x: i32) -> i32:
            return x + 1

        """)
        assert mod.inc.w_func.is_force_inline

    def test_arg_evaluated_once(self):
        # arg expressions are bound via VarDef so they run exactly once
        mod = self.compile("""
        from __spy__ import force_inline

        var calls: i32 = 0

        def bump() -> i32:
            calls = calls + 1
            return calls

        @force_inline
        def double(x: i32) -> i32:
            return x + x

        def foo() -> i32:
            return double(bump())
        """)
        assert mod.foo() == 2
        assert mod.calls == 1

    def test_error_applied_to_blue_function(self):
        src = """
        from __spy__ import force_inline

        @force_inline
        @blue
        def inc(x: i32) -> i32:
            return x + 1

        def foo(x: i32) -> i32:
            return inc(x)
        """
        errors = expect_errors(
            "@force_inline cannot be applied to @blue functions",
        )
        self.compile_raises(src, "foo", errors, error_reporting="eager")

    def test_none_return_type(self):
        mod = self.compile("""
        from __spy__ import force_inline

        @force_inline
        def greet(x: i32) -> None:
            print(x)

        def foo() -> None:
            greet(42)
        """)
        mod.foo()

    def test_error_missing_return(self):
        src = """
        from __spy__ import force_inline

        @force_inline
        def inc(x: i32) -> i32:
            var y = x + 1

        def foo() -> i32:
            return inc(3)
        """
        errors = expect_errors(
            "@force_inline requires a single tail return",
        )
        self.compile_raises(src, "foo", errors, error_reporting="eager")

    def test_error_multiple_returns(self):
        src = """
        from __spy__ import force_inline

        @force_inline
        def clamp(x: i32, lo: i32) -> i32:
            if x < lo:
                return lo
            return x

        def foo() -> i32:
            return clamp(3, 0)
        """
        errors = expect_errors(
            "@force_inline requires a single tail return",
            ("`return` must be the last statement of the body", "return lo"),
        )
        self.compile_raises(src, "foo", errors, error_reporting="eager")

    @skip_backends("interp", reason="recursion detected at redshift time, not interp")
    def test_error_recursive_inline(self):
        src = """
        from __spy__ import force_inline

        @force_inline
        def fact(n: i32) -> i32:
            return fact(n - 1)

        def foo() -> i32:
            return fact(5)
        """
        errors = expect_errors(
            "cannot inline a recursive call to @force_inline function `test::fact#__bare__`",
        )
        self.compile_raises(src, "foo", errors, error_reporting="eager")

    def test_binop_cmpop_unaryop(self):
        mod = self.compile("""
        from __spy__ import force_inline

        @force_inline
        def compute(x: i32) -> bool:
            var y = x + 1
            y = y * 2
            return not (y == x - 1)

        def foo() -> bool:
            return compute(3)
        """)
        assert mod.foo() is True

    def test_if_stmt(self):
        mod = self.compile("""
        from __spy__ import force_inline

        @force_inline
        def abs_val(x: i32) -> i32:
            var y = x
            if x < 0:
                y = -x
            return y

        def foo() -> i32:
            return abs_val(-5)
        """)
        assert mod.foo() == 5

    def test_while_stmt(self):
        mod = self.compile("""
        from __spy__ import force_inline

        @force_inline
        def sum_to(n: i32) -> i32:
            var result = 0
            var i = 0
            while i < n:
                result = result + i
                i = i + 1
            return result

        def foo() -> i32:
            return sum_to(4)
        """)
        assert mod.foo() == 6

    def test_getitem(self):
        mod = self.compile("""
        from __spy__ import force_inline

        @force_inline
        def first(xs: list[i32]) -> i32:
            return xs[0]

        def foo() -> i32:
            var xs: list[i32] = [10, 20, 30]
            return first(xs)
        """)
        assert mod.foo() == 10

    def test_logical_and_or(self):
        mod = self.compile("""
        from __spy__ import force_inline

        @force_inline
        def both(a: bool, b: bool) -> bool:
            return a and b

        @force_inline
        def either(a: bool, b: bool) -> bool:
            return a or b

        def foo() -> bool:
            return both(True, False) or either(False, True)
        """)
        assert mod.foo() is True

    def test_str_const(self):
        mod = self.compile("""
        from __spy__ import force_inline

        @force_inline
        def greet() -> str:
            return 'hello'

        def foo() -> str:
            return greet()
        """)
        assert mod.foo() == "hello"

    def test_tuple(self):
        mod = self.compile("""
        from __spy__ import force_inline

        @force_inline
        def pair(x: i32, y: i32) -> tuple[i32, i32]:
            return (x, y)

        def foo() -> i32:
            var t = pair(3, 4)
            return t[0] + t[1]
        """)
        assert mod.foo() == 7

    def test_getattr(self):
        mod = self.compile("""
        from __spy__ import force_inline

        @struct
        class Point:
            x: i32
            y: i32

        @force_inline
        def get_x(p: Point) -> i32:
            return p.x

        def foo() -> i32:
            var p = Point(10, 20)
            return get_x(p)
        """)
        assert mod.foo() == 10

    def test_loop_with_break(self):
        mod = self.compile("""
        from __spy__ import force_inline

        @force_inline
        def find_first(n: i32) -> i32:
            var i = 0
            var result = -1
            while i < n:
                if i > 1:
                    result = i
                    i = n
                i = i + 1
            return result

        def foo() -> i32:
            return find_first(5)
        """)
        assert mod.foo() == 2

    def test_assignexpr(self):
        mod = self.compile("""
        from __spy__ import force_inline

        @force_inline
        def inc_and_get(x: i32) -> i32:
            return x + 1

        def foo() -> i32:
            var y: i32 = 0
            var z = inc_and_get(y := 5)
            return y + z
        """)
        assert mod.foo() == 11

    def test_outer_var(self):
        mod = self.compile("""
        from __spy__ import force_inline

        var counter: i32 = 0

        @force_inline
        def bump_and_get() -> i32:
            counter = counter + 1
            return counter

        def foo() -> i32:
            return bump_and_get() + bump_and_get()
        """)
        assert mod.foo() == 3

    def test_pass(self):
        mod = self.compile("""
        from __spy__ import force_inline

        @force_inline
        def noop() -> None:
            pass

        def foo() -> None:
            noop()
        """)
        mod.foo()

    def test_break_continue(self):
        mod = self.compile("""
        from __spy__ import force_inline

        @force_inline
        def count_odd(n: i32) -> i32:
            var result = 0
            var i = 0
            while i < n:
                i = i + 1
                if i % 2 == 0:
                    continue
                result = result + 1
            return result

        def foo() -> i32:
            return count_odd(6)
        """)
        assert mod.foo() == 3

    def test_raise(self):
        src = """
        from __spy__ import force_inline

        @force_inline
        def check(x: i32) -> i32:
            if x < 0:
                raise ValueError('negative')
            return x

        def foo() -> i32:
            return check(5)
        """
        mod = self.compile(src)
        assert mod.foo() == 5

    def test_nested_force_inline(self):
        mod = self.compile("""
        from __spy__ import force_inline

        @force_inline
        def add1(x: i32) -> i32:
            return x + 1

        @force_inline
        def add2(x: i32) -> i32:
            return add1(add1(x))

        def foo() -> i32:
            return add2(10)
        """)
        assert mod.foo() == 12

    def test_assignexpr_walrus_in_body(self):
        mod = self.compile("""
        from __spy__ import force_inline

        def get_val() -> i32:
            return 7

        @force_inline
        def use_walrus() -> i32:
            var x: i32 = 0
            var y = (x := get_val()) + x
            return y

        def foo() -> i32:
            return use_walrus()
        """)
        assert mod.foo() == 14

    def test_assignexpr_in_body(self):
        mod = self.compile("""
        from __spy__ import force_inline

        @force_inline
        def compute(x: i32) -> i32:
            var items: list[i32] = [x, x + 1, x + 2]
            var result: i32 = 0
            var i = 0
            while i < 3:
                result = result + items[i]
                i = i + 1
            return result

        def foo() -> i32:
            return compute(10)
        """)
        assert mod.foo() == 33

    def test_metafunc(self):
        # see also test_doppler.py:test_force_inline_in_metafunc
        mod = self.compile("""
        from __spy__ import force_inline
        from operator import OpSpec

        @blue.metafunc
        def double(m_x):
            @force_inline
            def impl(x: i32) -> i32:
                return x + x
            return OpSpec(impl)

        def foo() -> i32:
            return double(21)
        """)
        assert mod.foo() == 42
