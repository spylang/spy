"""
Tests for load/store with __builtin_memcpy when alignment < alignof(T).
"""

import pytest

from spy.tests.support import CompilerTest


class TestUnderAligned(CompilerTest):
    @pytest.fixture(params=["raw", "gc"])
    def memkind(self, request):
        return request.param

    def test_under_aligned_roundtrip(self, memkind):
        k = memkind
        mod = self.compile(f"""
            from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr
            def foo[T]() -> T:
                p: k_ptr[T, 1] = k_alloc[T, 1](3)
                p[0] = 10; p[1] = 20; p[2] = 30
                return p[0] + p[1] + p[2]

            foo_i32 = foo[i32]
            foo_f64 = foo[f64]
            """)
        assert mod.foo_i32() == 60
        assert mod.foo_f64() == 60.0

    def test_weaken_to_under_aligned(self):
        mod = self.compile("""
            from unsafe import gc_alloc, gc_ptr
            def foo[T]() -> T:
                p_aligned: gc_ptr[T] = gc_alloc[T](2)
                p1: gc_ptr[T, 1] = p_aligned
                p1[0] = 99; p1[1] = -7
                return p1[0] - p1[1]

            foo_i32 = foo[i32]
            foo_f64 = foo[f64]
            """)
        assert mod.foo_i32() == 106
        assert mod.foo_f64() == 106.0

    def test_struct_field_roundtrip(self):
        mod = self.compile("""
            from unsafe import gc_alloc, gc_ptr
            @struct
            class Point:
                x: i32
                y: i32
            def foo() -> i32:
                p: gc_ptr[Point, 1] = gc_alloc[Point, 1](2)
                p[0].x = 1; p[0].y = 2
                p[1].x = 3; p[1].y = 4
                return p[0].x + 10*p[0].y + 100*p[1].x + 1000*p[1].y
            """)
        assert mod.foo() == 4321

    def test_struct_field_weakening(self):
        mod = self.compile("""
            from unsafe import gc_alloc, gc_ptr
            @struct
            class Point:
                x: i32
                y: i32
            def foo() -> i32:
                p32: gc_ptr[Point, 32] = gc_alloc[Point, 32](1)
                p1: gc_ptr[Point, 1] = p32
                p1[0].x = 100; p1[0].y = 200
                return p1[0].x + p1[0].y
            """)
        assert mod.foo() == 300
