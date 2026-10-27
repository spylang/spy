import pytest

from spy.tests.support import CompilerTest, expect_errors, only_interp
from spy.vm.b import B
from spy.vm.modules.unsafe.misc import NATURAL_ALIGNMENT, alignof
from spy.vm.modules.unsafe.ptr import W_PtrType

# Alignment value guaranteed to exceed SPY_BASE_ALIGNMENT on all targets
# (16 on native-64, 8 on wasm).
OVER_ALIGNMENT = 32


@pytest.fixture(params=["raw", "gc"])
def memkind(request):
    return request.param


class TestUnsafePtrAlignment(CompilerTest):
    def test_different_alignments_are_different_types(self):
        src = """
        from unsafe import gc_ptr, align

        def same_alignment() -> bool:
            return gc_ptr[i32, align(8)] is gc_ptr[i32, align(8)]

        def different_alignment() -> bool:
            return gc_ptr[i32, align(8)] is gc_ptr[i32, align(16)]
        """
        mod = self.compile(src)
        assert mod.same_alignment()
        assert not mod.different_alignment()

    def test_too_many_arguments(self):
        src = """
        from unsafe import gc_ptr, align

        def foo() -> None:
            p: gc_ptr[i32, align(8), align(16)]
        """
        errors = expect_errors("gc_ptr accepts 1 or 2 arguments, got 3")
        self.compile_raises(src, "foo", errors)

    def test_bare_int_is_not_an_alignment(self):
        src = """
        from unsafe import gc_ptr

        def foo() -> None:
            p: gc_ptr[i32, 8]
        """
        errors = expect_errors("gc_ptr: alignment must be `align(N)`, got `i32`")
        self.compile_raises(src, "foo", errors)

    @pytest.mark.parametrize("bad", [0, -1, 3, 6])
    def test_align_must_be_power_of_two(self, bad):
        src = f"""
        from unsafe import align

        def foo() -> None:
            align(3)
        """
        errors = expect_errors(f"align(3): the alignment must be a power of two")
        self.compile_raises(src, "foo", errors)

    def test_natural_and_explicit_alignof_are_distinct_but_convertible(self):
        src = """
        from unsafe import gc_ptr, gc_alloc, align

        def same_type() -> bool:
            return gc_ptr[i32] is gc_ptr[i32, align(4)]

        def foo() -> i32:
            p: gc_ptr[i32] = gc_alloc[i32](1)
            q: gc_ptr[i32, align(4)] = p   # natural -> explicit
            q[0] = 42
            r: gc_ptr[i32] = q             # explicit -> natural
            return r[0]
        """
        mod = self.compile(src)
        assert not mod.same_type()
        assert mod.foo() == 42

    def test_natural_to_weaker_explicit(self):
        src = """
        from unsafe import gc_ptr, gc_alloc, align

        def foo() -> i32:
            p: gc_ptr[i32] = gc_alloc[i32](1)
            q: gc_ptr[i32, align(1)] = p   # 1 <= alignof(i32)
            q[0] = 7
            return q[0]
        """
        mod = self.compile(src)
        assert mod.foo() == 7

    def test_explicit_to_natural_strengthening_is_a_type_error(self):
        src = """
            from unsafe import gc_ptr, gc_alloc, align

            def foo() -> None:
                p: gc_ptr[i32, align(2)] = gc_alloc[i32, align(2)](1)
                q: gc_ptr[i32] = p   # 4 > 2: needs align_cast
            """
        errors = expect_errors(
            "mismatched types",
            (
                "expected `unsafe::gc_ptr[i32]`, got `unsafe::gc_ptr[i32, align(2)]`",
                "p",
            ),
            (
                "expected `unsafe::gc_ptr[i32]` because of type declaration",
                "gc_ptr[i32]",
            ),
        )
        self.compile_raises(src, "foo", errors)

    def test_fwdecl_natural_alignment(self):
        # a self-referential struct: when `gc_ptr[Point]` is created inside
        # the body, Point is not defined yet, so we cannot know alignof(Point)
        src = """
        from unsafe import gc_ptr, gc_alloc, align

        @struct
        class Point:
            x: i32
            y: i32
            next: gc_ptr[Point]

        def same_as_align_1() -> bool:
            return gc_ptr[Point] is gc_ptr[Point, align(1)]

        def same_as_align_4() -> bool:
            return gc_ptr[Point] is gc_ptr[Point, align(4)]

        def foo() -> i32:
            p: gc_ptr[Point] = gc_alloc[Point](2)
            p[0].x = 1
            p[0].next = p
            p[0].next[0].y = 2
            q: gc_ptr[Point, align(4)] = p
            return q[0].x + 10 * q[0].y
        """
        mod = self.compile(src)
        assert not mod.same_as_align_1()
        assert not mod.same_as_align_4()
        assert mod.foo() == 21

    def test_weakening_is_implicit(self):
        src = """
        from unsafe import gc_alloc, gc_ptr, align

        def foo() -> i32:
            p16: gc_ptr[i32, align(16)] = gc_alloc[i32, align(16)](1)
            # implicit weakening: gc_ptr[i32, align(16)] -> gc_ptr[i32, align(8)]
            p8: gc_ptr[i32, align(8)] = p16
            p8[0] = 123
            return p8[0]
        """
        mod = self.compile(src)
        assert mod.foo() == 123

    def test_strengthening_is_a_type_error(self):
        src = """
        from unsafe import gc_alloc, gc_ptr, align

        def foo() -> None:
            p8: gc_ptr[i32, align(8)] = gc_alloc[i32, align(8)](1)
            p16: gc_ptr[i32, align(16)] = p8
        """
        errors = expect_errors(
            "mismatched types",
            (
                "expected `unsafe::gc_ptr[i32, align(16)]`, got `unsafe::gc_ptr[i32, align(8)]`",
                "p8",
            ),
            (
                "expected `unsafe::gc_ptr[i32, align(16)]` because of type declaration",
                "gc_ptr[i32, align(16)]",
            ),
        )
        self.compile_raises(src, "foo", errors)

    def test_under_aligned_roundtrip(self, memkind):
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, align
        def foo[T]() -> T:
            p: k_ptr[T, align(1)] = k_alloc[T, align(1)](3)
            p[0] = 10; p[1] = 20; p[2] = 30
            return p[0] + p[1] + p[2]

        foo_i32 = foo[i32]
        foo_f64 = foo[f64]
        """
        mod = self.compile(src)
        assert mod.foo_i32() == 60
        assert mod.foo_f64() == 60.0

    def test_weaken_to_under_aligned(self):
        src = """
        from unsafe import gc_alloc, gc_ptr, align
        def foo[T]() -> T:
            p_aligned: gc_ptr[T] = gc_alloc[T](2)
            p1: gc_ptr[T, align(1)] = p_aligned
            p1[0] = 99; p1[1] = -7
            return p1[0] - p1[1]

        foo_i32 = foo[i32]
        foo_f64 = foo[f64]
        """
        mod = self.compile(src)
        assert mod.foo_i32() == 106
        assert mod.foo_f64() == 106.0

    def test_struct_field_roundtrip(self):
        src = """
        from unsafe import gc_alloc, gc_ptr, align
        @struct
        class Point:
            x: i32
            y: i32
        def foo() -> i32:
            p: gc_ptr[Point, align(1)] = gc_alloc[Point, align(1)](2)
            p[0].x = 1; p[0].y = 2
            p[1].x = 3; p[1].y = 4
            return p[0].x + 10*p[0].y + 100*p[1].x + 1000*p[1].y
        """
        mod = self.compile(src)
        assert mod.foo() == 4321

    def test_struct_field_weakening(self):
        src = """
        from unsafe import gc_alloc, gc_ptr, align
        @struct
        class Point:
            x: i32
            y: i32
        def foo() -> i32:
            p32: gc_ptr[Point, align(32)] = gc_alloc[Point, align(32)](1)
            p1: gc_ptr[Point, align(1)] = p32
            p1[0].x = 100; p1[0].y = 200
            return p1[0].x + p1[0].y
        """
        mod = self.compile(src)
        assert mod.foo() == 300

    # exercise the over-allocation path

    def test_ptr_address_is_aligned(self, memkind):
        k = memkind
        N = OVER_ALIGNMENT
        src = f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, ptr_to_addr, align

        def alloc() -> k_ptr[i32, align({N})]:
            p = k_alloc[i32, align({N})](4)
            assert ptr_to_addr(p) % {N} == 0
            return p
        """
        mod = self.compile(src)
        mod.alloc()

    def test_over_alloc_roundtrip(self, memkind):
        k = memkind
        N = OVER_ALIGNMENT
        src = f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, align

        def foo() -> i32:
            p: k_ptr[i32, align({N})] = k_alloc[i32, align({N})](3)
            p[0] = 10
            p[1] = 20
            p[2] = 30
            return p[0] + p[1] + p[2]
        """
        mod = self.compile(src)
        assert mod.foo() == 60

    def test_over_alloc_struct(self, memkind):
        k = memkind
        N = OVER_ALIGNMENT
        src = f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, align

        @struct
        class Point:
            x: i32
            y: i32

        def foo() -> i32:
            p: k_ptr[Point, align({N})] = k_alloc[Point, align({N})](2)
            p[0].x = 1
            p[0].y = 2
            p[1].x = 3
            p[1].y = 4
            return p[0].x + 10*p[0].y + 100*p[1].x + 1000*p[1].y
        """
        mod = self.compile(src)
        assert mod.foo() == 4321

    def test_over_alloc_weakening(self):
        N = OVER_ALIGNMENT
        src = f"""
        from unsafe import gc_alloc, gc_ptr, align

        def foo() -> i32:
            p32: gc_ptr[i32, align({N})] = gc_alloc[i32, align({N})](1)
            # implicit weakening: gc_ptr[i32, align({N})] -> gc_ptr[i32, align(8)]
            p8: gc_ptr[i32, align(8)] = p32
            p8[0] = 99
            return p8[0]
        """
        mod = self.compile(src)
        assert mod.foo() == 99

    def test_over_alloc_multiple_are_aligned(self):
        # Multiple independent over-aligned allocations should all be
        # properly aligned (not just the first one)
        N = OVER_ALIGNMENT
        src = f"""
        from unsafe import gc_alloc, gc_ptr, ptr_to_addr, align

        def alloc() -> gc_ptr[i32, align({N})]:
            p = gc_alloc[i32, align({N})](1)
            assert ptr_to_addr(p) % {N} == 0
            return p

        def foo() -> i32:
            a = alloc()
            b = alloc()
            c = alloc()
            a[0] = 1
            b[0] = 2
            c[0] = 3
            return a[0] + b[0] + c[0]
        """
        mod = self.compile(src)
        assert mod.foo() == 6
        # a few more independent allocations, for extra confidence
        for _ in range(3):
            mod.alloc()

    def test_over_alloc_f64(self):
        N = OVER_ALIGNMENT
        src = f"""
        from unsafe import gc_alloc, gc_ptr, align

        def foo() -> f64:
            p: gc_ptr[f64, align({N})] = gc_alloc[f64, align({N})](2)
            p[0] = 1.5
            p[1] = 2.5
            return p[0] + p[1]
        """
        mod = self.compile(src)
        assert mod.foo() == 4.0

    def test_over_alloc_address_is_aligned_f64(self):
        N = OVER_ALIGNMENT
        src = f"""
        from unsafe import gc_alloc, gc_ptr, ptr_to_addr, align

        def alloc() -> gc_ptr[f64, align({N})]:
            p = gc_alloc[f64, align({N})](2)
            assert ptr_to_addr(p) % {N} == 0
            return p
        """
        mod = self.compile(src)
        mod.alloc()

    @only_interp
    def test_natural_vs_explicit_alignment(self):
        # gc_ptr[T] means "natural alignment" (internally -1): it is a
        # DIFFERENT type than gc_ptr[T, align(alignof(T))]
        src = """
        from unsafe import gc_ptr, align, alignof

        def get_natural() -> type:
            return gc_ptr[f64]

        def get_explicit() -> type:
            return gc_ptr[f64, align(alignof(f64))]
        """
        mod = self.compile(src)
        w_natural = mod.get_natural(unwrap=False)
        assert w_natural is mod.get_natural(unwrap=False)
        w_explicit = mod.get_explicit(unwrap=False)
        assert w_natural is not w_explicit

        N = alignof(B.w_f64)
        assert isinstance(w_natural, W_PtrType)
        assert isinstance(w_explicit, W_PtrType)
        assert w_natural.alignment == NATURAL_ALIGNMENT
        assert w_natural.resolved_alignment() == N
        assert w_explicit.resolved_alignment() == N
        assert repr(w_natural) == "<spy type 'unsafe::gc_ptr[f64]'>"
        assert repr(w_explicit) == "<spy type 'unsafe::gc_ptr[f64, align(8)]'>"
