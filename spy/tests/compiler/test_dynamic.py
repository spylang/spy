import pytest
from spy.errors import SPyTypeError
from spy.vm.builtins import B
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

    ## def test_dynamic(self):
    ##     mod = self.compile("""
    ##     def get_x() -> dynamic:
    ##         return 41

    ##     def foo() -> i32:
    ##         return get_x() + 1
    ##     """)
    ##     assert mod.foo() == 42
