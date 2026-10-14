import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest, expect_errors, only_interp


class TestSIMD(CompilerTest):
    def test_already_aligned(self):
        src = """
        from simd import align_offset
        from unsafe import gc_alloc, align, align_cast

        def aligned() -> i32:
            p = gc_alloc[i32, align(16)](10)
            return align_offset(p, 16, 10)

        def weak_tag() -> i32:
            # The declared alignment is only 1, but the real address is
            # 16-aligned: align_offset looks at the runtime address.
            strong = gc_alloc[i32, align(16)](10)
            weak = align_cast[1](strong)
            return align_offset(weak, 16, 10)
        """
        mod = self.compile(src)
        assert mod.aligned() == 0
        assert mod.weak_tag() == 0

    def test_computes_correct_offset(self):
        src = """
        from simd import align_offset
        from unsafe import gc_alloc, ptr_to_addr

        def foo(align: i32) -> tuple[i32, i32]:
            p = gc_alloc[i32](20)
            return align_offset(p, align, 20), ptr_to_addr(p)
        """
        mod = self.compile(src)
        sizeof_i32 = 4
        for align in [4, 16, 64]:
            offset, addr = mod.foo(align)
            assert 0 <= offset < align // sizeof_i32
            assert (addr + sizeof_i32 * offset) % align == 0

    def test_trivial_cases(self):
        src = """
        from simd import align_offset
        from unsafe import gc_alloc, gc_ptr

        def clamped_to_n() -> i32:
            # A buffer of 3 items can't reach a 1 MiB boundary: the result
            # is clamped to n.
            p = gc_alloc[i32](3)
            return align_offset(p, 1048576, 3)

        def clamped_to_zero() -> i32:
            p = gc_alloc[i32](0)
            return align_offset(p, 4096, 0)

        def align_is_1() -> i32:
            p = gc_alloc[i32](10)
            return align_offset(p, 1, 10)

        def null_pointer() -> i32:
            # NULL (addr 0) is aligned to anything
            p = gc_ptr[i32].NULL
            return align_offset(p, 4096, 10)
        """
        mod = self.compile(src)
        assert mod.clamped_to_n() == 3
        assert mod.clamped_to_zero() == 0
        assert mod.align_is_1() == 0
        assert mod.null_pointer() == 0

    def test_non_power_of_two_N_panics(self):
        src = """
        from simd import align_offset
        from unsafe import gc_alloc

        def foo(align: i32) -> i32:
            p = gc_alloc[i32](50)
            return align_offset(p, align, 50)
        """
        mod = self.compile(src)
        with pytest.raises(SPyError):
            mod.foo(24)

    @only_interp
    def test_non_power_of_two_N_compile_error(self):
        src = """
        from simd import align_offset
        from unsafe import gc_alloc

        def foo() -> i32:
            p = gc_alloc[i32](50)
            return align_offset(p, 24, 50)
        """
        mod = self.compile(src)
        self.compile_raises(src, "foo", expect_errors("align must be a power of two"))
