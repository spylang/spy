import re

import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest, skip_backends


@skip_backends("C", reason="dynamic not supported")
class TestDynamic(CompilerTest):
    def test_upcast_and_downcast(self):
        # this is similar to the same test in test_basic, but it uses
        # `dynamic` instead of `object`
        mod = self.compile("""
        def foo() -> i32:
            x: i32 = 1
            y: dynamic = x
            return y
        """)
        assert mod.foo() == 1

    def test_downcast_error(self):
        # NOTE: we don't check this with expect_errors because this is ALWAYS
        # a runtime error. The compilation always succeed.
        mod = self.compile("""
        def foo() -> str:
            x: i32 = 1
            var y: dynamic = x
            return y
        """)
        msg = "Invalid cast. Expected `str`, got `i32`"
        with SPyError.raises("W_TypeError", match=msg):
            mod.foo()

    def test_dynamic_dispatch_ok(self):
        mod = self.compile("""
        def foo() -> i32:
            x: dynamic = 1
            y: dynamic = 2
            return x + y
        """)
        assert mod.foo() == 3

    def test_dynamic_runtime_error(self):
        mod = self.compile("""
        def foo() -> i32:
            var x: dynamic = 1
            var y: dynamic = 'hello'
            return x + y
        """)
        msg = re.escape("cannot do `i32` + `str`")
        with SPyError.raises("W_TypeError", match=msg):
            mod.foo()

    def test_mixed_dispatch(self):
        mod = self.compile("""
        def foo() -> i32:
            x: dynamic = 1
            y: i32 = 2
            return x + y
        """)
        assert mod.foo() == 3

    def test_binop(self):
        mod = self.compile("""
        def add(x: dynamic, y: dynamic) -> dynamic:      return x  + y
        def sub(x: dynamic, y: dynamic) -> dynamic:      return x  - y
        def mul(x: dynamic, y: dynamic) -> dynamic:      return x  * y
        def mod(x: dynamic, y: dynamic) -> dynamic:      return x  % y
        def div(x: dynamic, y: dynamic) -> dynamic:      return x  / y
        def floordiv(x: dynamic, y: dynamic) -> dynamic: return x // y
        """)
        assert mod.add(1, 1) == 2
        assert mod.sub(7, 3) == 4
        assert mod.mul(5, 6) == 30
        assert mod.mod(10, 3) == 1
        assert mod.div(11, 2) == 5.5
        assert mod.floordiv(11, 2) == 5

    def test_bitwise(self):
        mod = self.compile("""
        def shl(x: dynamic, y: dynamic) -> dynamic:   return x << y
        def shr(x: dynamic, y: dynamic) -> dynamic:   return x >> y
        def b_and(x: dynamic, y: dynamic) -> dynamic: return x  & y
        def b_or(x: dynamic, y: dynamic) -> dynamic:  return x  | y
        def b_xor(x: dynamic, y: dynamic) -> dynamic: return x  ^ y
        """)
        assert mod.shl(2, 5) == 2 << 5
        assert mod.shr(32, 5) == 32 >> 5
        assert mod.b_and(7, 3) == 7 & 3
        assert mod.b_and(127, 7) == 127 & 7
        assert mod.b_or(127, 123) == 127 | 123
        assert mod.b_or(127, 0) == 127 | 0
        assert mod.b_xor(16, 15) == 16 ^ 15
        assert mod.b_xor(16, 0) == 16 ^ 0

    def test_cmp(self):
        mod = self.compile("""
        def eq (x: dynamic, y: dynamic) -> dynamic: return x == y
        def neq(x: dynamic, y: dynamic) -> dynamic: return x != y
        def lt (x: dynamic, y: dynamic) -> dynamic: return x  < y
        def lte(x: dynamic, y: dynamic) -> dynamic: return x <= y
        def gt (x: dynamic, y: dynamic) -> dynamic: return x  > y
        def gte(x: dynamic, y: dynamic) -> dynamic: return x >= y
        """)
        assert mod.eq(5, 5) is True
        assert mod.eq(5, 6) is False
        #
        assert mod.neq(5, 5) is False
        assert mod.neq(5, 6) is True
        #
        assert mod.lt(5, 6) is True
        assert mod.lt(5, 5) is False
        assert mod.lt(6, 5) is False
        #
        assert mod.lte(5, 6) is True
        assert mod.lte(5, 5) is True
        assert mod.lte(6, 5) is False
        #
        assert mod.gt(5, 6) is False
        assert mod.gt(5, 5) is False
        assert mod.gt(6, 5) is True
        #
        assert mod.gte(5, 6) is False
        assert mod.gte(5, 5) is True
        assert mod.gte(6, 5) is True

    def test_call(self):
        mod = self.compile("""
        def inc(x: i32) -> i32:
            return x + 1

        def get_inc() -> dynamic:
            return inc

        def foo() -> i32:
            return get_inc()(7)
        """)
        assert mod.foo() == 8

    def test_wrong_call(self):
        mod = self.compile("""
        def get_inc() -> dynamic:
            return 'hello'

        def foo() -> i32:
            return get_inc()(7)
        """)
        msg = "cannot call objects of type `str`"
        with SPyError.raises("W_TypeError", match=msg):
            mod.foo()

    def test_setattr(self):
        mod = self.compile("""
        x: i32 = 0

        @blue
        def __INIT__(mod: dynamic):
            mod.x = 42
        """)
        vm = self.vm
        assert mod.x == 42

    def test_wrong_setattr(self):
        if self.backend == "doppler":
            pytest.skip("fixme")

        mod = self.compile("""
        def foo() -> None:
            obj: dynamic = "hello"
            obj.x = 42
        """)
        msg = "type `str` does not support assignment to attribute 'x'"
        with SPyError.raises("W_TypeError", match=msg):
            mod.foo()

    def test_getattr(self):
        mod = self.compile("""
        x: i32 = 42
        y: i32 = 0

        @blue
        def __INIT__(mod: dynamic):
            mod.y = mod.x + 1
        """)
        vm = self.vm
        assert mod.x == 42
        assert mod.y == 43

    def test_print(self, capfd):
        mod = self.compile("""
        def dyn(x: dynamic) -> dynamic:
            return x

        def foo() -> None:
            print(dyn("hello world"))
            print(dyn(42))
            print(dyn(12.3))
            print(dyn(True))
            print(dyn(None))
        """)
        mod.foo()
        out, err = capfd.readouterr()
        assert out == "\n".join(
            [
                "hello world",
                "42",
                "12.3",
                "True",
                "None",
                "",
            ]
        )
