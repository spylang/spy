"""
Tests for the spy_alloc_aligned_impl C helper function.

These tests exercise the *over-allocation* path: when the requested
alignment exceeds SPY_BASE_ALIGNMENT (16 on native-64, 8 on wasm), the
allocator can no longer rely on the base allocator's guarantee and must
over-allocate, round the pointer up, and discard the base pointer.
"""

import pytest

from spy.tests.support import CompilerTest
from spy.tests.wasm_wrapper import WasmPtr
from spy.vm.modules.unsafe.ptr import W_Ptr

# Alignment value guaranteed to exceed SPY_BASE_ALIGNMENT on all targets
# (16 on native-64, 8 on wasm).
OVER_ALIGNMENT = 32


@pytest.fixture(params=["raw", "gc"])
def memkind(request):
    return request.param


class TestOverAllocAlignment(CompilerTest):
    def _get_addr(self, p: W_Ptr | WasmPtr) -> int:
        """Extract the raw address from a returned pointer."""
        if self.backend in ("interp", "doppler"):
            assert isinstance(p, W_Ptr)
            return p.addr
        else:
            assert isinstance(p, WasmPtr)
            return p.addr

    def test_ptr_address_is_aligned(self, memkind):
        k = memkind
        mod = self.compile(
            """
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr

        def alloc() -> k_ptr[i32, {N}]:
            return k_alloc[i32, {N}](4)
        """.format(k=k, N=OVER_ALIGNMENT)
        )
        p = mod.alloc()
        addr = self._get_addr(p)
        assert addr % OVER_ALIGNMENT == 0, (
            f"expected {OVER_ALIGNMENT}-byte aligned address, got {addr}"
        )

    def test_over_alloc_roundtrip(self, memkind):
        k = memkind
        mod = self.compile(
            """
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr

        def foo() -> i32:
            p: k_ptr[i32, {N}] = k_alloc[i32, {N}](3)
            p[0] = 10
            p[1] = 20
            p[2] = 30
            return p[0] + p[1] + p[2]
        """.format(k=k, N=OVER_ALIGNMENT)
        )
        assert mod.foo() == 60

    def test_over_alloc_struct(self, memkind):
        k = memkind
        mod = self.compile(
            """
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr

        @struct
        class Point:
            x: i32
            y: i32

        def foo() -> i32:
            p: k_ptr[Point, {N}] = k_alloc[Point, {N}](2)
            p[0].x = 1
            p[0].y = 2
            p[1].x = 3
            p[1].y = 4
            return p[0].x + 10*p[0].y + 100*p[1].x + 1000*p[1].y
        """.format(k=k, N=OVER_ALIGNMENT)
        )
        assert mod.foo() == 4321

    def test_over_alloc_weakening(self):
        mod = self.compile(
            """
        from unsafe import gc_alloc, gc_ptr

        def foo() -> i32:
            p32: gc_ptr[i32, {N}] = gc_alloc[i32, {N}](1)
            # implicit weakening: gc_ptr[i32, {N}] -> gc_ptr[i32, 8]
            p8: gc_ptr[i32, 8] = p32
            p8[0] = 99
            return p8[0]
        """.format(N=OVER_ALIGNMENT)
        )
        assert mod.foo() == 99

    def test_over_alloc_multiple_are_aligned(self):
        # Multiple independent over-aligned allocations should all be
        # properly aligned (not just the first one)
        mod = self.compile(
            """
        from unsafe import gc_alloc, gc_ptr

        def alloc() -> gc_ptr[i32, {N}]:
            return gc_alloc[i32, {N}](1)

        def foo() -> i32:
            a = alloc()
            b = alloc()
            c = alloc()
            a[0] = 1
            b[0] = 2
            c[0] = 3
            return a[0] + b[0] + c[0]
        """.format(N=OVER_ALIGNMENT)
        )
        assert mod.foo() == 6
        # verify that each individual allocation is aligned
        for _ in range(3):
            p = mod.alloc()
            addr = self._get_addr(p)
            assert addr % OVER_ALIGNMENT == 0

    def test_over_alloc_f64(self):
        mod = self.compile(
            """
        from unsafe import gc_alloc, gc_ptr

        def foo() -> f64:
            p: gc_ptr[f64, {N}] = gc_alloc[f64, {N}](2)
            p[0] = 1.5
            p[1] = 2.5
            return p[0] + p[1]
        """.format(N=OVER_ALIGNMENT)
        )
        assert mod.foo() == 4.0

    def test_over_alloc_address_is_aligned_f64(self):
        mod = self.compile(
            """
        from unsafe import gc_alloc, gc_ptr

        def alloc() -> gc_ptr[f64, {N}]:
            return gc_alloc[f64, {N}](2)
        """.format(N=OVER_ALIGNMENT)
        )
        p = mod.alloc()
        addr = self._get_addr(p)
        assert addr % OVER_ALIGNMENT == 0, (
            f"expected {OVER_ALIGNMENT}-byte aligned address, got {addr}"
        )
