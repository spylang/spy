import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest


@pytest.fixture(params=["raw", "gc"])
def memkind(request):
    return request.param


class TestCastAlign(CompilerTest):
    # =========================================================================
    # cast[DstItemT](ptr)
    # =========================================================================

    def test_cast_same_type(self, memkind):
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, cast

        def foo() -> i32:
            p: k_ptr[i32] = k_alloc[i32](10)
            q: k_ptr[i32] = cast[i32](p)
            q[9] = 123
            return q[9]

        def length() -> i32:
            p = k_alloc[i32](10)
            return cast[i32](p)._debug_get_length()
        """
        mod = self.compile(src)
        assert mod.foo() == 123
        assert mod.length() == 10

    def test_cast_out_of_bounds_panics(self, memkind):
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, cast

        def foo() -> i32:
            p = k_alloc[i32](10)
            q = cast[i32](p)
            return q[10]
        """
        mod = self.compile(src)
        with SPyError.raises("W_PanicError"):
            mod.foo()

    def test_cast_same_size_types(self, memkind):
        # i32 <-> f32: the length is preserved exactly
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, cast

        def foo() -> i32:
            p: k_ptr[i32] = k_alloc[i32](10)
            q: k_ptr[f32] = cast[f32](p)
            return q._debug_get_length()
        """
        mod = self.compile(src)
        assert mod.foo() == 10

    def test_cast_to_larger_type_truncates(self, memkind):
        """10 i8 = 10 bytes; i32 is 4 bytes -> new length = 10 // 4 = 2."""
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, cast, align

        def length() -> i32:
            p: k_ptr[i8, align(4)] = k_alloc[i8, align(4)](10)
            q: k_ptr[i32] = cast[i32](p)
            return q._debug_get_length()

        def foo() -> i32:
            p: k_ptr[i8, align(4)] = k_alloc[i8, align(4)](10)
            q: k_ptr[i32] = cast[i32](p)
            q[1] = 5
            return q[1]
        """
        mod = self.compile(src)
        assert mod.length() == 2
        assert mod.foo() == 5

    def test_cast_to_smaller_type(self, memkind):
        # 10 i32 = 40 bytes; i8 is 1 byte -> new length = 40
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, cast, align

        def length() -> i32:
            p: k_ptr[i32] = k_alloc[i32](10)
            q: k_ptr[i8, align(4)] = cast[i8](p)
            return q._debug_get_length()

        def foo() -> i32:
            p: k_ptr[i32] = k_alloc[i32](10)
            q: k_ptr[i8, align(4)] = cast[i8](p)
            q[39] = 7
            return q[39]
        """
        mod = self.compile(src)
        assert mod.length() == 40
        assert mod.foo() == 7

    def test_cast_preserves_alignment(self, memkind):
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, cast, align

        def foo() -> bool:
            p: k_ptr[i32, align(16)] = k_alloc[i32, align(16)](10)
            q = cast[f32](p)
            return type(q) is k_ptr[f32, align(16)]
        """
        mod = self.compile(src)
        assert mod.foo()

    def test_cast_preserves_address(self, memkind):
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, cast, ptr_to_addr

        def foo() -> bool:
            p: k_ptr[i32] = k_alloc[i32](10)
            q: k_ptr[f32] = cast[f32](p)
            return ptr_to_addr(p) == ptr_to_addr(q)
        """
        mod = self.compile(src)
        assert mod.foo()

    def test_cast_null_pointer(self, memkind):
        k = memkind
        src = f"""
        from unsafe import {k}_ptr as k_ptr, cast, ptr_to_addr

        def addr() -> i32:
            p: k_ptr[i32] = k_ptr[i32].NULL
            q: k_ptr[f32] = cast[f32](p)
            return ptr_to_addr(q)

        def length() -> i32:
            p: k_ptr[i32] = k_ptr[i32].NULL
            q: k_ptr[f32] = cast[f32](p)
            return q._debug_get_length()
        """
        mod = self.compile(src)
        assert mod.addr() == 0
        assert mod.length() == 0

    def test_cast_zero_length(self, memkind):
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, cast

        def length() -> i32:
            p = k_alloc[i32](0)
            return cast[i8](p)._debug_get_length()

        def foo() -> i32:
            p = k_alloc[i32](0)
            return cast[i32](p)[0]
        """
        mod = self.compile(src)
        assert mod.length() == 0
        with SPyError.raises("W_PanicError"):
            mod.foo()

    def test_cast_chain(self, memkind):
        # 16 i8 -> 4 i32 -> 2 i64
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, cast, align

        def lengths() -> i32:
            p: k_ptr[i8, align(8)] = k_alloc[i8, align(8)](16)
            q: k_ptr[i32, align(8)] = cast[i32](p)
            r: k_ptr[i64, align(8)] = cast[i64](q)
            return 100 * q._debug_get_length() + r._debug_get_length()

        def foo() -> i64:
            p: k_ptr[i8, align(8)] = k_alloc[i8, align(8)](16)
            r = cast[i64](cast[i32](p))
            r[1] = 9
            return r[1]
        """
        mod = self.compile(src)
        assert mod.lengths() == 402
        assert mod.foo() == 9

    # =========================================================================
    # align_cast[N](ptr)
    # =========================================================================

    def test_align_cast_weaken(self, memkind):
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, align_cast, align

        def foo() -> i32:
            p: k_ptr[i32, align(16)] = k_alloc[i32, align(16)](10)
            q: k_ptr[i32, align(4)] = align_cast[4](p)
            q[9] = 1
            return q[9] + q._debug_get_length()
        """
        mod = self.compile(src)
        assert mod.foo() == 11

    def test_align_cast_same(self, memkind):
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, align_cast, align

        def foo() -> i32:
            p: k_ptr[i32, align(8)] = k_alloc[i32, align(8)](10)
            q: k_ptr[i32, align(8)] = align_cast[8](p)
            q[9] = 1
            return q[9] + q._debug_get_length()
        """
        mod = self.compile(src)
        assert mod.foo() == 11

    def test_align_cast_strengthen_when_actually_aligned(self, memkind):
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, align_cast, align

        def foo() -> i32:
            strong: k_ptr[i8, align(4096)] = k_alloc[i8, align(4096)](1)
            weak: k_ptr[i8, align(1)] = strong
            back: k_ptr[i8, align(4096)] = align_cast[4096](weak)
            return back._debug_get_length()
        """
        mod = self.compile(src)
        assert mod.foo() == 1

    def test_align_cast_strengthen_invalid_panics(self, memkind):
        # A 1-byte allocation has no reason to land on a 4096-byte boundary;
        # claiming that alignment should panic (this isn't a mathematical
        # certainty but is as close as we can get without exposing pointer
        # arithmetic).
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, align_cast, align

        def foo() -> i32:
            p: k_ptr[i8, align(1)] = k_alloc[i8, align(1)](1)
            q: k_ptr[i8, align(4096)] = align_cast[4096](p)
            return q[0]
        """
        mod = self.compile(src)
        with SPyError.raises("W_PanicError", match="not aligned"):
            mod.foo()

    def test_align_cast_preserves_address(self, memkind):
        k = memkind
        src = f"""
        from unsafe import (
            {k}_alloc as k_alloc, {k}_ptr as k_ptr, align_cast, align, ptr_to_addr
        )

        def foo() -> bool:
            p: k_ptr[i32, align(4)] = k_alloc[i32, align(4)](10)
            q: k_ptr[i32, align(8)] = align_cast[8](p)
            return ptr_to_addr(p) == ptr_to_addr(q)
        """
        mod = self.compile(src)
        assert mod.foo()

    def test_align_cast_preserves_type_and_length(self, memkind):
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, align_cast, align

        def foo() -> i32:
            p: k_ptr[i32, align(4)] = k_alloc[i32, align(4)](10)
            q: k_ptr[i32, align(8)] = align_cast[8](p)
            q[0] = 42
            return q[0] + q._debug_get_length()
        """
        mod = self.compile(src)
        assert mod.foo() == 52

    def test_align_cast_null_pointer(self, memkind):
        # NULL (addr 0) satisfies any alignment, so this never panics
        k = memkind
        src = f"""
        from unsafe import {k}_ptr as k_ptr, align_cast, align, ptr_to_addr

        def foo() -> i32:
            p: k_ptr[i32] = k_ptr[i32].NULL
            q: k_ptr[i32, align(16)] = align_cast[16](p)
            return ptr_to_addr(q)
        """
        mod = self.compile(src)
        assert mod.foo() == 0

    def test_compose_cast_and_align_cast(self, memkind):
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, cast, align_cast, align

        def foo() -> i32:
            p: k_ptr[i32, align(4)] = k_alloc[i32, align(4)](10)
            q: k_ptr[f32, align(4)] = cast[f32](p)
            r: k_ptr[f32, align(8)] = align_cast[8](q)
            r[9] = 1.0
            return r._debug_get_length()
        """
        mod = self.compile(src)
        assert mod.foo() == 10

    def test_align_cast_chain(self, memkind):
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, align_cast, align

        def foo() -> i32:
            p: k_ptr[i32, align(4)] = k_alloc[i32, align(4)](10)
            q: k_ptr[i32, align(8)] = align_cast[8](p)
            r: k_ptr[i32, align(16)] = align_cast[16](q)
            r[9] = 1
            return r[9] + r._debug_get_length()
        """
        mod = self.compile(src)
        assert mod.foo() == 11
