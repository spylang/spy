#-*- encoding: utf-8 -*-

import struct
import pytest
from spy.vm.b import B
from spy.tests.support import CompilerTest, skip_backends, no_backend, no_C

class TestSPyCFFI(CompilerTest):

    @no_C
    def test_field(self):
        mod = self.compile(
        """
        from spy_cffi import Field

        def foo() -> Field:
            return Field('x', 8, i32)
        """)
        w_f = mod.foo()
        assert self.vm.unwrap(w_f.w_name) == 'x'
        assert self.vm.unwrap(w_f.w_offset) == 8
        assert w_f.w_type is B.w_i32
