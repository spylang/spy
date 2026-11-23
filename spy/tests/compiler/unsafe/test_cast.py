import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest, expect_errors


@pytest.fixture(params=["raw", "gc"])
def memkind(request):
    return request.param


class TestCastAlign(CompilerTest):
    def test_cast_simd(self, memkind):
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, cast, align
        from _simd import SIMD

        def foo() -> tuple[f32, f32, i32, f32, i32]:
            p = k_alloc[f32, align(16)](10)
            for i in range(10):
                p[i] = f32(i)

            # q.length = p.length // 4; equals to 2, the last 2 f32 are unreachable
            q: k_ptr[SIMD[f32, 4], align(16)] = cast[SIMD[f32, 4]](p)
            v = q[1]  # p[4:8]
            q[0] = SIMD[f32, 4].splat(9.0)

            # r.length r = q.length * 4 = 8
            r: k_ptr[f32, align(16)] = cast[f32](q)
            return v[0], v[3], q._debug_get_length(), r[2], r._debug_get_length()
        """
        mod = self.compile(src)
        v0, v3, q_length, r2, r_length = mod.foo()
        assert (v0, v3) == (4.0, 7.0)
        assert q_length == 2
        assert r2 == 9.0
        assert r_length == 8

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
        from unsafe import {k}_alloc as k_alloc, cast, align
        from _simd import SIMD

        def bad() -> None:
            p = k_alloc[{src_T}, align(16)](8)
            q = cast[{dst_T}](p)
        """
        self.compile_raises(src, "bad", expect_errors("invalid cast"))

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
