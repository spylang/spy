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

    def test_OpImpl_with_args(self):
        mod = self.compile(
        """
        from operator import OpImpl, OpArg

        def bar(x: i32) -> i32:
            return x * 2

        @blue
        def foo() -> OpImpl:
            # Create an OpImpl with an argument list
            arg = OpArg('blue', i32, 42)
            return OpImpl(bar, [arg])
        """)
        w_opimpl = mod.foo(unwrap=False)
        assert isinstance(w_opimpl, W_OpImpl)
        assert not w_opimpl.is_simple()
        assert w_opimpl._args_wop is not None
        assert len(w_opimpl._args_wop) == 1

        # Check the OpArg stored in the arguments list
        wop = w_opimpl._args_wop[0]
        assert isinstance(wop, W_OpArg)
        assert wop.color == 'blue'
        assert wop.w_static_type is B.w_i32
        assert wop.is_blue()
        assert wop._w_val is not None
        assert self.vm.unwrap_i32(wop._w_val) == 42

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

    def test_oparg_properties(self):
        mod = self.compile(
        """
        from operator import OpArg

        def foo() -> tuple:
            arg = OpArg('blue', i32, 42)
            return (arg.color, arg.static_type, arg.blueval)
        """)
        w_tup = mod.foo(unwrap=False)
        w_color, w_type, w_blueval = w_tup.items_w
        assert self.vm.unwrap_str(w_color) == 'blue'
        assert w_type is B.w_i32
        assert self.vm.unwrap_i32(w_blueval) == 42

    def test_opimpl_null(self):
        mod = self.compile(
        """
        from operator import OpImpl

        @blue
        def get_null() -> OpImpl:
            return OpImpl.NULL
        """)
        w_null = mod.get_null(unwrap=False)
        assert w_null is W_OpImpl.NULL
