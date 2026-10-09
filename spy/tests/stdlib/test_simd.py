import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest


class TestSIMD(CompilerTest):
    @pytest.fixture(params=["raw", "gc"])
    def memkind(self, request):
        return request.param

    def test_already_aligned(self, memkind):
        k = memkind
        src = f"""
        from simd import align_offset
        from unsafe import {k}_alloc, {k}_ptr, align, align_cast

        def aligned() -> i32:
            p: {k}_ptr[i32, align(16)] = {k}_alloc[i32, align(16)](10)
            return align_offset(p, 16, 10)

        def weak_tag() -> i32:
            # The declared alignment is only 1, but the real address is
            # 16-aligned: align_offset looks at the runtime address, not
            # at the static alignment.
            strong: {k}_ptr[i32, align(16)] = {k}_alloc[i32, align(16)](10)
            weak: {k}_ptr[i32, align(1)] = align_cast[1](strong)
            return align_offset(weak, 16, 10)
        """
        mod = self.compile(src)
        assert mod.aligned() == 0
        assert mod.weak_tag() == 0

    def test_computes_correct_offset(self, memkind):
        k = memkind
        src = f"""
        from simd import align_offset
        from unsafe import {k}_alloc, {k}_ptr, ptr_to_addr

        def foo(N: i32) -> tuple[i32, i32]:
            p: {k}_ptr[i32] = {k}_alloc[i32](20)
            return align_offset(p, N, 20), ptr_to_addr(p)
        """
        mod = self.compile(src)
        for N in [4, 16, 64]:
            offset, addr = mod.foo(N)
            assert 0 <= offset < N // 4
            assert (addr + 4 * offset) % N == 0

    def test_trivial_cases(self, memkind):
        k = memkind
        src = f"""
        from simd import align_offset
        from unsafe import {k}_alloc, {k}_ptr

        def clamped_to_n() -> i32:
            # A buffer of 3 items can't reach a 1 MiB boundary: the result
            # is clamped to n, so a `for i in range(offset)` peeling loop
            # never goes out of bounds.
            p: {k}_ptr[i32] = {k}_alloc[i32](3)
            return align_offset(p, 1048576, 3)

        def zero_n() -> i32:
            p: {k}_ptr[i32] = {k}_alloc[i32](0)
            return align_offset(p, 4096, 0)

        def N_is_1() -> i32:
            p: {k}_ptr[i32] = {k}_alloc[i32](10)
            return align_offset(p, 1, 10)

        def null_pointer() -> i32:
            # NULL (addr 0) is aligned to anything
            p: {k}_ptr[i32] = {k}_ptr[i32].NULL
            return align_offset(p, 4096, 10)
        """
        mod = self.compile(src)
        assert mod.clamped_to_n() == 3
        assert mod.zero_n() == 0
        assert mod.N_is_1() == 0
        assert mod.null_pointer() == 0

    def test_non_power_of_two_N_panics(self, memkind):
        k = memkind
        src = f"""
        from simd import align_offset
        from unsafe import {k}_alloc, {k}_ptr

        def foo() -> i32:
            p: {k}_ptr[i32] = {k}_alloc[i32](50)
            return align_offset(p, 24, 50)
        """
        mod = self.compile(src)
        with pytest.raises(SPyError):
            mod.foo()
