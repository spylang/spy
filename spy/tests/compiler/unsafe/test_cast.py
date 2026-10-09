import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest, expect_errors


@pytest.fixture(params=["raw", "gc"])
def memkind(request):
    return request.param


class TestCastAlign(CompilerTest):
    # =========================================================================
    # cast[DstItemT](ptr)
    #
    # Only the casts which are useful for SIMD are allowed:
    #     ptr[T]          -> ptr[SIMD[T, N]]
    #     ptr[SIMD[T, N]] -> ptr[T]
    # Everything else is a compile-time error.
    # =========================================================================

    def test_cast_simd(self, memkind):
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, cast, align
        from _simd import SIMD

        def foo() -> tuple[f32, f32, i32, f32, i32]:
            p: k_ptr[f32, align(16)] = k_alloc[f32, align(16)](10)
            for i in range(10):
                p[i] = f32(i)

            # f32 -> SIMD[f32, 4]: 10 f32 = 40 bytes; a vector is 16 bytes
            # -> new length = 40 // 16 = 2 (the last 2 f32 are unreachable)
            q: k_ptr[SIMD[f32, 4], align(16)] = cast[SIMD[f32, 4]](p)
            v = q[1]  # p[4:8]
            q[0] = SIMD[f32, 4].splat(9.0)

            # SIMD[f32, 4] -> f32: 2 vectors = 32 bytes -> new length = 8
            r: k_ptr[f32, align(16)] = cast[f32](q)
            return v[0], v[3], q._debug_get_length(), r[2], r._debug_get_length()
        """
        mod = self.compile(src)
        assert mod.foo() == (4.0, 7.0, 2, 9.0, 8)

    def test_cast_simd_all_dtypes(self, memkind):
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, cast, align
        from _simd import SIMD

        def func[T](x: T) -> tuple[T, i32]:
            p: k_ptr[T, align(16)] = k_alloc[T, align(16)](4)
            q = cast[SIMD[T, 2]](p)
            q[1] = SIMD[T, 2].splat(x)
            return p[3], q._debug_get_length()

        rt_i8 = func[i8]
        rt_u8 = func[u8]
        rt_i32 = func[i32]
        rt_u32 = func[u32]
        rt_i64 = func[i64]
        rt_u64 = func[u64]
        rt_f32 = func[f32]
        rt_f64 = func[f64]
        """
        mod = self.compile(src)
        assert mod.rt_i8(-5) == (-5, 2)
        assert mod.rt_u8(200) == (200, 2)
        assert mod.rt_i32(-42) == (-42, 2)
        assert mod.rt_u32(42) == (42, 2)
        assert mod.rt_i64(-42) == (-42, 2)
        assert mod.rt_u64(42) == (42, 2)
        assert mod.rt_f32(1.5) == (1.5, 2)
        assert mod.rt_f64(1.5) == (1.5, 2)

    def test_cast_out_of_bounds_panics(self, memkind):
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, cast, align
        from _simd import SIMD

        def foo() -> i32:
            p = k_alloc[i32, align(16)](10)
            q = cast[SIMD[i32, 4]](p)  # length is 2
            return q[2][0]
        """
        mod = self.compile(src)
        with SPyError.raises("W_PanicError"):
            mod.foo()

    def test_cast_null_pointer(self, memkind):
        k = memkind
        src = f"""
        from unsafe import {k}_ptr as k_ptr, cast, align, ptr_to_addr
        from _simd import SIMD

        def foo() -> tuple[i32, i32]:
            p: k_ptr[f32, align(16)] = k_ptr[f32, align(16)].NULL
            q: k_ptr[SIMD[f32, 4], align(16)] = cast[SIMD[f32, 4]](p)
            return ptr_to_addr(q), q._debug_get_length()
        """
        mod = self.compile(src)
        assert mod.foo() == (0, 0)

    def test_cast_zero_length(self, memkind):
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, cast, align
        from _simd import SIMD

        def length() -> i32:
            p = k_alloc[i32, align(16)](0)
            return cast[SIMD[i32, 4]](p)._debug_get_length()

        def foo() -> i32:
            p = k_alloc[i32, align(16)](0)
            return cast[SIMD[i32, 4]](p)[0][0]
        """
        mod = self.compile(src)
        assert mod.length() == 0
        with SPyError.raises("W_PanicError"):
            mod.foo()

    # -------------------------------------------------------------------------
    # forbidden casts
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize(
        "src_T, dst_T",
        [
            # scalar <-> scalar: reinterpreting memory is not allowed
            ("i32", "f32"),
            ("f32", "i32"),
            ("i32", "i8"),
            ("i8", "i32"),
            ("u32", "i32"),
            ("f64", "i64"),
            # same type: not a useful cast
            ("i32", "i32"),
            # scalar -> SIMD with another lane type
            ("i32", "SIMD[f32, 4]"),
            ("i8", "SIMD[i32, 4]"),
            # SIMD -> scalar of another lane type
            ("SIMD[i32, 4]", "f32"),
            ("SIMD[i32, 4]", "i8"),
            # SIMD <-> SIMD: neither the lane type nor the size can change
            ("SIMD[i32, 4]", "SIMD[f32, 4]"),
            ("SIMD[i32, 4]", "SIMD[i32, 8]"),
            ("SIMD[i32, 4]", "SIMD[i32, 4]"),
        ],
    )
    def test_cast_forbidden(self, memkind, src_T, dst_T):
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, cast, align
        from _simd import SIMD

        def bad() -> None:
            p: k_ptr[{src_T}, align(16)] = k_alloc[{src_T}, align(16)](8)
            q = cast[{dst_T}](p)
        """
        self.compile_raises(src, "bad", expect_errors("invalid cast"))

    def test_cast_forbidden_struct(self, memkind):
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, cast, align
        from _simd import SIMD

        @struct
        class Point:
            x: i32
            y: i32

        def bad() -> None:
            p: k_ptr[Point, align(16)] = k_alloc[Point, align(16)](4)
            q = cast[i32](p)
        """
        self.compile_raises(src, "bad", expect_errors("invalid cast"))

    def test_cast_forbidden_not_a_ptr(self):
        src = """
        from unsafe import cast

        def bad() -> None:
            x = cast[f32](42)
        """
        self.compile_raises(src, "bad", expect_errors("mismatched types"))

    # =========================================================================
    # align_cast[N](ptr)
    # =========================================================================

    def test_align_cast(self, memkind):
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, align_cast, align

        def weaken() -> tuple[i32, i32]:
            p: k_ptr[i32, align(16)] = k_alloc[i32, align(16)](10)
            q: k_ptr[i32, align(4)] = align_cast[4](p)
            q[9] = 1
            return q[9], q._debug_get_length()

        def same() -> tuple[i32, i32]:
            p: k_ptr[i32, align(8)] = k_alloc[i32, align(8)](10)
            q: k_ptr[i32, align(8)] = align_cast[8](p)
            q[9] = 2
            return q[9], q._debug_get_length()

        def strengthen_when_aligned() -> tuple[i8, i32]:
            strong: k_ptr[i8, align(4096)] = k_alloc[i8, align(4096)](1)
            strong[0] = 3
            weak: k_ptr[i8, align(1)] = strong
            back: k_ptr[i8, align(4096)] = align_cast[4096](weak)
            return back[0], back._debug_get_length()
        """
        mod = self.compile(src)
        assert mod.weaken() == (1, 10)
        assert mod.same() == (2, 10)
        assert mod.strengthen_when_aligned() == (3, 1)

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

    def test_align_cast_null_pointer(self, memkind):
        # NULL (addr 0) satisfies any alignment, so this never panics
        k = memkind
        src = f"""
        from unsafe import {k}_ptr as k_ptr, align_cast, align, ptr_to_addr

        def foo() -> tuple[i32, i32]:
            p: k_ptr[i32] = k_ptr[i32].NULL
            q: k_ptr[i32, align(16)] = align_cast[16](p)
            return ptr_to_addr(q), q._debug_get_length()
        """
        mod = self.compile(src)
        assert mod.foo() == (0, 0)
