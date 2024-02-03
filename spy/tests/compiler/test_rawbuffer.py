#-*- encoding: utf-8 -*-

import pytest
from spy.tests.support import CompilerTest, skip_backends, no_backend

class TestRawBuffer(CompilerTest):

    def test_simple(self):
        mod = self.compile(
        """
        from rawbuffer import RawBuffer, rb_alloc, rb_set_i32, rb_get_i32

        def foo() -> i32:
            buf: RawBuffer = rb_alloc(8)
            rb_set_i32(buf, 0, 42)
            return rb_get_i32(buf, 0)
        """)
        assert mod.foo() == 42
