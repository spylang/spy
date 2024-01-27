import re
import pytest
from spy.errors import SPyTypeError
from spy.vm.b import B
from spy.tests.support import CompilerTest, skip_backends,  expect_errors

@skip_backends('C', reason='dynamic not supported')
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
            y: dynamic = x
            return y
        """)
        msg = "Invalid cast. Expected `str`, got `i32`"
        with pytest.raises(SPyTypeError, match=msg):
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
            x: dynamic = 1
            y: dynamic = 'hello'
            return x + y
        """)
        msg = re.escape('cannot do `i32` + `str`')
        with pytest.raises(SPyTypeError, match=msg):
            mod.foo()

    def test_mixed_dispatch(self):
        mod = self.compile("""
        def foo() -> i32:
            x: dynamic = 1
            y: i32 = 2
            return x + y
        """)
        assert mod.foo() == 3

    def test_other_ops(self):
        mod = self.compile("""
        def mul(x: dynamic, y: dynamic) -> dynamic: return x  * y
        def eq (x: dynamic, y: dynamic) -> dynamic: return x == y
        def neq(x: dynamic, y: dynamic) -> dynamic: return x != y
        def lt (x: dynamic, y: dynamic) -> dynamic: return x  < y
        def lte(x: dynamic, y: dynamic) -> dynamic: return x <= y
        def gt (x: dynamic, y: dynamic) -> dynamic: return x  > y
        def gte(x: dynamic, y: dynamic) -> dynamic: return x >= y
        """)
        assert mod.mul(5, 6) == 30
        #
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
        if self.backend == 'doppler':
            pytest.skip('fixme')

        mod = self.compile("""
        def inc(x: i32) -> i32:
            return x + 1

        @blue
        def get_inc() -> dynamic:
            return inc

        def foo() -> i32:
            return get_inc()(7)
        """)
        assert mod.foo() == 8

    def test_wrong_call(self):
        if self.backend == 'doppler':
            pytest.skip('fixme')

        mod = self.compile("""
        @blue
        def get_inc() -> dynamic:
            return 'hello'

        def foo() -> i32:
            return get_inc()(7)
        """)
        msg = 'cannot call objects of type `str`'
        with pytest.raises(SPyTypeError, match=msg):
            mod.foo()
