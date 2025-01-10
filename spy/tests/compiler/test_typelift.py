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
        WORKAROUND: i32 = 0

        @typelift
        class MyInt:
            __inner__: i32

        def get() -> type:
            return MyInt
        """)
        w_myint = mod.get(unwrap=False)
        assert repr(w_myint) == "<spy type 'test::MyInt' (lifted from 'i32' )>"

    def test_from_and_to(self):
        mod = self.compile("""
        @typelift
        class MyInt:
            __inner__: i32

        def box(i: i32) -> MyInt:
            return MyInt.from_inner(i)

        def unbox(m: MyInt) -> i32:
            return m.__inner__

        def call_unbox(i: i32) -> i32:
            return unbox(box(i))

        """)
        myint = mod.box(42)
        assert myint.llval == 42
        assert myint.w_hltype.fqn.fullname == 'test::MyInt'
        assert mod.call_unbox(43) == 43
