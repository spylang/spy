#-*- encoding: utf-8 -*-

from spy.vm.b import B
from spy.vm.opspec import W_OpSpec, W_MetaArg
from spy.vm.opimpl import W_OpImpl
from spy.tests.support import CompilerTest, only_interp, expect_errors

@only_interp
class TestOpSpec(CompilerTest):

    def test_new_OpSpec(self):
        mod = self.compile(
        """
        from operator import OpSpec

        def bar() -> None:
            pass

        @blue
        def foo() -> OpSpec:
            return OpSpec(bar)
        """)
        w_opspec = mod.foo(unwrap=False)
        assert isinstance(w_opspec, W_OpSpec)
        assert w_opspec._w_func is mod.bar.w_func
        assert w_opspec.is_simple()

    def test_OpSpec_with_args(self):
        mod = self.compile(
        """
        from operator import OpSpec, OpArg

        def bar(x: i32) -> i32:
            return x * 2

        @blue
        def foo() -> OpSpec:
            # Create an OpSpec with an argument list
            arg = OpArg('blue', i32, 42)
            return OpSpec(bar, [arg])
        """)
        w_opspec = mod.foo(unwrap=False)
        assert isinstance(w_opspec, W_OpSpec)
        assert not w_opspec.is_simple()
        assert w_opspec._args_wam is not None
        assert len(w_opspec._args_wam) == 1

        # Check the OpArg stored in the arguments list
        wop = w_opspec._args_wam[0]
        assert isinstance(wop, W_MetaArg)
        assert wop.color == 'blue'
        assert wop.w_static_T is B.w_i32
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
        assert isinstance(w_blue_oparg, W_MetaArg)
        assert w_blue_oparg.color == 'blue'
        assert w_blue_oparg.w_static_T is B.w_i32
        assert w_blue_oparg._w_val is not None

        # Test red OpArg creation
        w_red_oparg = mod.create_red_oparg(unwrap=False)
        assert isinstance(w_red_oparg, W_MetaArg)
        assert w_red_oparg.color == 'red'
        assert w_red_oparg.w_static_T is B.w_i32
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

    def test_opspec_null(self):
        mod = self.compile(
        """
        from operator import OpSpec

        @blue
        def get_null() -> OpSpec:
            return OpSpec.NULL
        """)
        w_null = mod.get_null(unwrap=False)
        assert w_null is W_OpSpec.NULL

    def test_oparg_from_type(self):
        mod = self.compile(
        """
        from operator import OpArg

        def foo() -> OpArg:
            return i32

        def bar() -> OpArg:
            return 42
        """)
        wam_x = mod.foo(unwrap=False)
        assert wam_x.color == 'red'
        assert wam_x.w_static_T is B.w_i32
        assert wam_x._w_val is None

        errors = expect_errors(
            'mismatched types',
            ('expected `operator::OpArg`, got `i32`', '42')
        )
        with errors:
            mod.bar()

    def test_call_OP_with_types(self):
        from spy.vm.modules.operator import OP
        mod = self.compile(
        """
        from operator import ADD, OpSpec

        def foo() -> dynamic:
            return ADD(i32, i32)
        """)
        w_opimpl = mod.foo(unwrap=False)
        assert isinstance(w_opimpl, W_OpImpl)
        assert w_opimpl.w_func is OP.w_i32_add
