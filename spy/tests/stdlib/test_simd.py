import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest, expect_errors, only_interp


class TestSIMD(CompilerTest):
    def test_align_offset(self):
        src = """
        from simd import align_offset
        from unsafe import gc_alloc, align, ptr_to_addr

        def already_aligned() -> i32:
            p = gc_alloc[i32, align(16)](10)
            return align_offset(p, 16, 10)

        def not_aligned(align: i32) -> tuple[i32, i32]:
            p = gc_alloc[i32](20)
            return align_offset(p, align, 20), ptr_to_addr(p)

        def clamped() -> i32:
            # a buffer of 3 items cannot reach a 1 MiB boundary: result is n
            p = gc_alloc[i32](3)
            return align_offset(p, 1048576, 3)
        """
        mod = self.compile(src)
        assert mod.already_aligned() == 0
        for align in [16, 64]:
            offset, addr = mod.not_aligned(align)
            assert 0 <= offset < align // 4
            assert (addr + 4 * offset) % align == 0
        assert mod.clamped() == 3

    def test_align_not_power_of_two(self):
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
    def test_align_not_power_of_two_blue(self):
        src = """
        from simd import align_offset
        from unsafe import gc_alloc

        def foo() -> i32:
            p = gc_alloc[i32](50)
            return align_offset(p, 24, 50)
        """
        self.compile_raises(src, "foo", expect_errors("align must be a power of two"))
