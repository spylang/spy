import re
import pytest
from spy.errors import SPyTypeError
from spy.fqn import FQN
from spy.vm.b import B
from spy.vm.function import W_ASTFunc
from spy.tests.support import (CompilerTest, skip_backends,  expect_errors,
                               only_interp)

class TestTypelift(CompilerTest):

    @only_interp
    def test_repr(self):
        mod = self.compile("""
        @typelift
        class MyInt:
            __ll__: i32

        def get() -> type:
            return MyInt
        """)
        w_myint = mod.get(unwrap=False)
        assert repr(w_myint) == "<spy type 'test::MyInt' (lifted from 'i32')>"

    def test_lift_and_lower(self):
        mod = self.compile("""
        @typelift
        class MyInt:
            __ll__: i32

        def lift(i: i32) -> MyInt:
            return MyInt.__lift__(i)

        def lower(m: MyInt) -> i32:
            return m.__ll__

        def call_lower(i: i32) -> i32:
            return lower(lift(i))

        """)
        myint = mod.lift(42)
        assert myint.llval == 42
        assert myint.w_hltype.fqn.fullname == 'test::MyInt'
        assert mod.call_lower(43) == 43
