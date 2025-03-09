#-*- encoding: utf-8 -*-

import pytest
from spy.libspy import SPyPanicError
from spy.vm.b import B
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.tests.support import CompilerTest, skip_backends, only_interp

@only_interp
class TestOpImpl(CompilerTest):

    def test_new_OpImpl(self):
        mod = self.compile(
        """
        from operator import OpImpl

        def bar() -> void:
            pass

        @blue
        def foo() -> OpImpl:
            return OpImpl(bar)
        """)
        w_opimpl = mod.foo(unwrap=False)
        assert isinstance(w_opimpl, W_OpImpl)
        assert w_opimpl._w_func is mod.bar.w_func
        assert w_opimpl.is_simple()

    def test_new_OpArg(self):
        mod = self.compile(
        """
        from operator import OpArg

        @blue
        def create_blue_oparg(x: i32) -> OpArg:
            return OpArg('blue', i32, x)

        @blue
        def create_red_oparg() -> OpArg:
            return OpArg('red', i32, None)
        """)

        # Test blue OpArg creation
        w_blue_oparg = mod.create_blue_oparg(42, unwrap=False)
        assert isinstance(w_blue_oparg, W_OpArg)
        assert w_blue_oparg.color == 'blue'
        assert w_blue_oparg.w_static_type is B.w_i32
        assert w_blue_oparg._w_val is not None

        # Test red OpArg creation
        w_red_oparg = mod.create_red_oparg(unwrap=False)
        assert isinstance(w_red_oparg, W_OpArg)
        assert w_red_oparg.color == 'red'
        assert w_red_oparg.w_static_type is B.w_i32
        assert w_red_oparg._w_val is None
