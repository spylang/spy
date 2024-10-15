#-*- encoding: utf-8 -*-

import pytest
from spy.errors import SPyPanicError
from spy.tests.support import CompilerTest, no_C

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

        def bar(i: i32) -> f64:
            # make sure that we can use other item types as well
            buf: ptr[f64] = gc_alloc(f64)(3)
            buf[0] = 1.2
            buf[1] = 3.4
            buf[2] = 5.6
            return buf[i]
        """)
        assert mod.foo() == 42
        assert mod.bar(0) == 1.2
        assert mod.bar(1) == 3.4
        assert mod.bar(2) == 5.6

    @no_C # WIP
    def test_out_of_bound(self):
        mod = self.compile(
        """
        from unsafe import gc_alloc, ptr

        def foo(i: i32) -> i32:
            buf: ptr[i32] = gc_alloc(i32)(3)
            buf[0] = 0
            buf[1] = 100
            buf[2] = 200
            return buf[i]
        """)
        assert mod.foo(1) == 100
        with pytest.raises(SPyPanicError, match="ptr_load out of bounds"):
            mod.foo(3)
