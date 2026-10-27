import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest


@pytest.fixture(params=["raw", "gc"])
def memkind(request):
    return request.param


class TestCastAlign(CompilerTest):
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
