"""
Tests for cast[DstItemT](ptr) and align_cast[N](ptr).

Note that ptr[T] has no app-level `.length` attribute (it's only accessible at
the interp/Python level, e.g. inside builtin funcs). So "did the length come
out right" is tested indirectly, via indexing: the last valid index must not
panic, and the first invalid index must panic.
"""

import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest


class TestCastAlign(CompilerTest):
    @pytest.fixture(params=["raw", "gc"])
    def memkind(self, request):
        return request.param

    # =========================================================================
    # cast[DstItemT](ptr)
    # =========================================================================

    def test_cast_same_type(self, memkind):
        k = memkind
        mod = self.compile(f"""
            from unsafe import {k}_alloc, {k}_ptr, cast
            def test() -> i32:
                p: {k}_ptr[i32] = {k}_alloc[i32](10)
                q: {k}_ptr[i32] = cast[i32](p)
                q[9] = 123  # last valid index for length 10
                return q[9]
            """)
        assert mod.test() == 123

    def test_cast_same_type_out_of_bounds_panics(self, memkind):
        k = memkind
        mod = self.compile(f"""
            from unsafe import {k}_alloc, {k}_ptr, cast
            def test() -> i32:
                p: {k}_ptr[i32] = {k}_alloc[i32](10)
                q: {k}_ptr[i32] = cast[i32](p)
                return q[10]  # length is still 10, so this is out of bounds
            """)
        with pytest.raises(SPyError):
            mod.test()

    def test_cast_same_size_types(self, memkind):
        """cast between same-size types (i32 <-> f32) preserves length exactly."""
        k = memkind
        mod = self.compile(f"""
            from unsafe import {k}_alloc, {k}_ptr, cast
            def test() -> i32:
                p: {k}_ptr[i32] = {k}_alloc[i32](10)
                q: {k}_ptr[f32] = cast[f32](p)
                q[9] = 1.0  # last valid index for length 10
                return 1
            """)
        assert mod.test() == 1

    def test_cast_to_larger_type_truncates(self, memkind):
        """10 i8 = 10 bytes; i32 is 4 bytes -> new length = 10 // 4 = 2."""
        k = memkind
        mod = self.compile(f"""
            from unsafe import {k}_alloc, {k}_ptr, cast
            def ok() -> i32:
                p: {k}_ptr[i8, 4] = {k}_alloc[i8, 4](10)
                q: {k}_ptr[i32] = cast[i32](p)
                q[1] = 5
                return q[1]
            def bad() -> i32:
                p: {k}_ptr[i8, 4] = {k}_alloc[i8, 4](10)
                q: {k}_ptr[i32] = cast[i32](p)
                return q[2]
            """)
        assert mod.ok() == 5
        with pytest.raises(SPyError):
            mod.bad()

    def test_cast_to_smaller_type_truncates(self, memkind):
        """10 i32 = 40 bytes; i8 is 1 byte -> new length = 40 // 1 = 40."""
        k = memkind
        mod = self.compile(f"""
            from unsafe import {k}_alloc, {k}_ptr, cast
            def ok() -> i32:
                p: {k}_ptr[i32] = {k}_alloc[i32](10)
                q: {k}_ptr[i8, 4] = cast[i8](p)
                q[39] = 7
                return q[39]
            def bad() -> i32:
                p: {k}_ptr[i32] = {k}_alloc[i32](10)
                q: {k}_ptr[i8, 4] = cast[i8](p)
                return q[40]
            """)
        assert mod.ok() == 7
        with pytest.raises(SPyError):
            mod.bad()

    def test_cast_preserves_alignment(self, memkind):
        k = memkind
        mod = self.compile(f"""
            from unsafe import {k}_alloc, {k}_ptr, cast
            def test() -> i32:
                p: {k}_ptr[i32, 16] = {k}_alloc[i32, 16](10)
                q: {k}_ptr[f32, 16] = cast[f32](p)
                return 1
            """)
        assert mod.test() == 1

    def test_cast_preserves_address(self, memkind):
        k = memkind
        mod = self.compile(f"""
            from unsafe import {k}_alloc, {k}_ptr, cast, ptr_to_addr
            def test() -> i32:
                p: {k}_ptr[i32] = {k}_alloc[i32](10)
                q: {k}_ptr[f32] = cast[f32](p)
                assert ptr_to_addr(p) == ptr_to_addr(q)
                return 1
            """)
        assert mod.test() == 1

    def test_cast_null_pointer(self, memkind):
        k = memkind
        mod = self.compile(f"""
            from unsafe import {k}_ptr, cast, ptr_to_addr
            def test() -> i32:
                p: {k}_ptr[i32] = {k}_ptr[i32].NULL
                q: {k}_ptr[f32] = cast[f32](p)
                return ptr_to_addr(q)
            """)
        assert mod.test() == 0

    def test_cast_zero_length(self, memkind):
        k = memkind
        mod = self.compile(f"""
            from unsafe import {k}_ptr, cast
            def test() -> i32:
                p: {k}_ptr[i32] = {k}_ptr[i32].NULL
                q: {k}_ptr[i32] = cast[i32](p)
                return q[0]
            """)
        with pytest.raises(SPyError):
            mod.test()

    def test_cast_chain(self, memkind):
        """16 i8 -> 4 i32 -> 2 i64, chaining casts."""
        k = memkind
        mod = self.compile(f"""
            from unsafe import {k}_alloc, {k}_ptr, cast
            def ok() -> i64:
                p: {k}_ptr[i8, 8] = {k}_alloc[i8, 8](16)
                q: {k}_ptr[i32, 8] = cast[i32](p)
                r: {k}_ptr[i64, 8] = cast[i64](q)
                r[1] = 9
                return r[1]
            def bad() -> i64:
                p: {k}_ptr[i8, 8] = {k}_alloc[i8, 8](16)
                q: {k}_ptr[i32, 8] = cast[i32](p)
                r: {k}_ptr[i64, 8] = cast[i64](q)
                return r[2]
            """)
        assert mod.ok() == 9
        with pytest.raises(SPyError):
            mod.bad()

    # =========================================================================
    # align_cast[N](ptr)
    # =========================================================================

    def test_align_cast_weaken(self, memkind):
        k = memkind
        mod = self.compile(f"""
            from unsafe import {k}_alloc, {k}_ptr, align_cast
            def test() -> i32:
                p: {k}_ptr[i32, 16] = {k}_alloc[i32, 16](10)
                q: {k}_ptr[i32, 4] = align_cast[4](p)
                q[9] = 1
                return q[9]
            """)
        assert mod.test() == 1

    def test_align_cast_same(self, memkind):
        k = memkind
        mod = self.compile(f"""
            from unsafe import {k}_alloc, {k}_ptr, align_cast
            def test() -> i32:
                p: {k}_ptr[i32, 8] = {k}_alloc[i32, 8](10)
                q: {k}_ptr[i32, 8] = align_cast[8](p)
                q[9] = 1
                return q[9]
            """)
        assert mod.test() == 1

    def test_align_cast_strengthen_when_actually_aligned(self, memkind):
        k = memkind
        mod = self.compile(f"""
            from unsafe import {k}_alloc, {k}_ptr, align_cast
            def test() -> i32:
                strong: {k}_ptr[i8, 4096] = {k}_alloc[i8, 4096](1)
                weak: {k}_ptr[i8, 1] = strong
                back: {k}_ptr[i8, 4096] = align_cast[4096](weak)
                return 1
            """)
        assert mod.test() == 1

    def test_align_cast_strengthen_invalid_panics(self, memkind):
        """
        A 1-byte allocation has no reason to land on a 4096-byte boundary;
        claiming that alignment should panic (this isn't a mathematical certainty
        but is as close as we can get without exposing pointer arithmetic).
        """
        k = memkind
        mod = self.compile(f"""
            from unsafe import {k}_alloc, {k}_ptr, align_cast
            def test() -> i32:
                p: {k}_ptr[i8, 1] = {k}_alloc[i8, 1](1)
                q: {k}_ptr[i8, 4096] = align_cast[4096](p)
                return q[0]
            """)
        with pytest.raises(SPyError):
            mod.test()

    def test_align_cast_preserves_address(self, memkind):
        k = memkind
        mod = self.compile(f"""
            from unsafe import {k}_alloc, {k}_ptr, align_cast, ptr_to_addr
            def test() -> i32:
                p: {k}_ptr[i32, 4] = {k}_alloc[i32, 4](10)
                q: {k}_ptr[i32, 8] = align_cast[8](p)
                assert ptr_to_addr(p) == ptr_to_addr(q)
                return 1
            """)
        assert mod.test() == 1

    def test_align_cast_preserves_type(self, memkind):
        k = memkind
        mod = self.compile(f"""
            from unsafe import {k}_alloc, {k}_ptr, align_cast
            def test() -> i32:
                p: {k}_ptr[i32, 4] = {k}_alloc[i32, 4](10)
                q: {k}_ptr[i32, 8] = align_cast[8](p)
                q[0] = 42
                return q[0]
            """)
        assert mod.test() == 42

    def test_align_cast_null_pointer(self, memkind):
        """NULL (addr 0) satisfies any alignment, so this never panics."""
        k = memkind
        mod = self.compile(f"""
            from unsafe import {k}_ptr, align_cast, ptr_to_addr
            def test() -> i32:
                p: {k}_ptr[i32] = {k}_ptr[i32].NULL
                q: {k}_ptr[i32, 16] = align_cast[16](p)
                return ptr_to_addr(q)
            """)
        assert mod.test() == 0

    def test_compose_cast_and_align_cast(self, memkind):
        k = memkind
        mod = self.compile(f"""
            from unsafe import {k}_alloc, {k}_ptr, cast, align_cast
            def test() -> i32:
                p: {k}_ptr[i32, 4] = {k}_alloc[i32, 4](10)
                q: {k}_ptr[f32, 4] = cast[f32](p)
                r: {k}_ptr[f32, 8] = align_cast[8](q)
                r[9] = 1.0
                return 1
            """)
        assert mod.test() == 1

    def test_align_cast_chain(self, memkind):
        k = memkind
        mod = self.compile(f"""
            from unsafe import {k}_alloc, {k}_ptr, align_cast
            def test() -> i32:
                p: {k}_ptr[i32, 4] = {k}_alloc[i32, 4](10)
                q: {k}_ptr[i32, 8] = align_cast[8](p)
                r: {k}_ptr[i32, 16] = align_cast[16](q)
                r[9] = 1
                return r[9]
            """)
        assert mod.test() == 1
