#-*- encoding: utf-8 -*-

import pytest
from spy.tests.support import CompilerTest, skip_backends, no_backend

class TestUnsafe(CompilerTest):

    def test_gc_alloc(self):
        mod = self.compile(
        """
        from unsafe import gc_alloc, ptr

        def foo() -> i32:
            # XXX: ideally we want gc_alloc[i32](1), but we can't for now
            #
            # XXX: ideally we would like the type of "buf" to be inferrable
            # but we can't for now because the return type of
            # gc_alloc(i32)(...) is `dynamic`
            #
            buf: ptr[i32] = gc_alloc(i32)(1)
            buf[0] = 42
            return buf[0]
        """)
        assert mod.foo() == 42
