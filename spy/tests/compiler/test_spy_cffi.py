#-*- encoding: utf-8 -*-

import struct
import pytest
from spy.vm.b import B
from spy.vm.modules.spy_cffi import CFFI
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

    @no_C
    def test_struct(self):
        mod = self.compile(
        """
        from spy_cffi import StructType, Field

        def make_Point() -> StructType:
            return StructType('Point', [
                Field('x', 0, i32),
                Field('y', 4, i32),
            ])
        """)
        pyclass = mod.make_Point()
        assert pyclass.__name__ == 'W_Point'
        assert pyclass.__qualname__ == 'W_Point'
        #
        w_Point = self.vm.wrap(pyclass)
        w_meta = self.vm.dynamic_type(w_Point)
        assert w_meta is CFFI.w_StructType
