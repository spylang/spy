import re
import pytest
from spy.errors import SPyTypeError
from spy.vm.b import B
from spy.tests.support import CompilerTest, skip_backends,  expect_errors

@skip_backends("C", reason="implement me")
class TestTypedef(CompilerTest):

    def test_cast_from_and_to(self):
        # XXX: for now we allow implicit coversion between a Typedef and it's
        # origin type because it's simpler, but eventually we want a more
        # explicit way, e.g. Typedef.cast or something like that.
        mod = self.compile("""
        from types import Typedef
        MyInt = Typedef('MyInt', i32)

        def foo() -> MyInt:
            x: MyInt = 42 # i32 -> MyInt
            return x

        def bar() -> i32:
            x: MyInt = 43 # i32 -> MyInt
            return x      # MyInt -> i32

        """)
        assert mod.foo() == 42
        assert mod.bar() == 43
