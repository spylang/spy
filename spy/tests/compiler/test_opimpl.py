#-*- encoding: utf-8 -*-

import pytest
from spy.libspy import SPyPanicError
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.tests.support import CompilerTest, skip_backends, only_interp

@only_interp
class TestOpImpl(CompilerTest):

    def test_simple(self):
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
