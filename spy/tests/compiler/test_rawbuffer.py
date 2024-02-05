#-*- encoding: utf-8 -*-

import struct
import pytest
from spy.tests.support import CompilerTest, skip_backends, no_backend

class TestRawBuffer(CompilerTest):

    def test_i32(self):
        mod = self.compile(
        """
        from rawbuffer import RawBuffer, rb_alloc, rb_set_i32, rb_get_i32

        def foo() -> i32:
            buf: RawBuffer = rb_alloc(4)
            rb_set_i32(buf, 0, 42)
            return rb_get_i32(buf, 0)
        """)
        assert mod.foo() == 42

    def test_f64(self):
        mod = self.compile(
        """
        from rawbuffer import RawBuffer, rb_alloc, rb_set_f64, rb_get_f64

        def foo() -> f64:
            buf: RawBuffer = rb_alloc(8)
            rb_set_f64(buf, 0, 12.3)
            return rb_get_f64(buf, 0)
        """)
        assert mod.foo() == 12.3

    def test_as_str(self):
        mod = self.compile(
        """
        from rawbuffer import (RawBuffer, rb_alloc, rb_set_i32,
                               rb_set_f64, rb_as_str)

        def foo() -> str:
            buf: RawBuffer = rb_alloc(16)
            rb_set_i32(buf, 0, 12)
            rb_set_i32(buf, 4, 34)
            rb_set_f64(buf, 8, 56.7)
            return rb_as_str(buf)
        """)
        s_buf = mod.foo()
        b_buf = s_buf.encode('latin-1')
        assert struct.unpack('iid', b_buf) == (12, 34, 56.7)
