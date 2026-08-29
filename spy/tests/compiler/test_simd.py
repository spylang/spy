import pytest

from spy.build.build_info import SIMD_ALLOWED_WIDTHS, SIMD_DEFAULT_WIDTH
from spy.build.config import resolve_simd_width
from spy.errors import SPyError
from spy.tests.support import CompilerTest, expect_errors, only_interp
from spy.vm.struct import UnwrappedStruct


def _as_tuple(unwrapped_tuple: UnwrappedStruct) -> tuple:
    return tuple(unwrapped_tuple._content.values())


class TestSIMD(CompilerTest):
    # === construction & validation (blue-time) ===

    def test_valid_sizes(self):
        # size must be a positive power of two: 1, 2, 4, 8 are all valid.
        mod = self.compile("""
            from _simd import SIMD

            def s1(x: f32) -> f32:
                v = SIMD[f32, 1](x)
                return v[0]

            def s2(x: f32) -> f32:
                v = SIMD[f32, 2](x)
                return v[1]

            def s4(x: f32) -> f32:
                v = SIMD[f32, 4](x)
                return v[2]

            def s8(x: i32) -> i32:
                v = SIMD[i32, 8](x)
                return v[7]
            """)
        assert mod.s1(1.5) == 1.5
        assert mod.s2(2.5) == 2.5
        assert mod.s4(3.5) == 3.5
        assert mod.s8(7) == 7

    def test_all_dtypes(self):
        # every v1 numeric primitive can be used as the lane dtype
        mod = self.compile("""
            from _simd import SIMD

            def f_i8(x: i32) -> i8:
                v = SIMD[i8, 4](i8(x))
                return v[0]

            def f_u8(x: i32) -> u8:
                v = SIMD[u8, 4](u8(x))
                return v[0]

            def f_i32(x: i32) -> i32:
                v = SIMD[i32, 4](x)
                return v[0]

            def f_u32(x: i32) -> u32:
                v = SIMD[u32, 4](u32(x))
                return v[0]

            def f_i64(x: i32) -> i64:
                v = SIMD[i64, 4](i64(x))
                return v[0]

            def f_u64(x: i32) -> u64:
                v = SIMD[u64, 4](u64(i64(x)))
                return v[0]

            def f_f32(x: f64) -> f32:
                v = SIMD[f32, 4](f32(x))
                return v[0]

            def f_f64(x: f64) -> f64:
                v = SIMD[f64, 4](x)
                return v[0]
            """)
        assert mod.f_i8(-5) == -5
        assert mod.f_u8(200) == 200
        assert mod.f_i32(42) == 42
        assert mod.f_u32(42) == 42
        assert mod.f_i64(42) == 42
        assert mod.f_u64(42) == 42
        assert mod.f_f32(1.5) == 1.5
        assert mod.f_f64(2.25) == 2.25

    # === SIMD[T, N].iota(): classmethod factory ===

    def test_iota_basic(self):
        # SIMD[T, N].iota() -> [0, 1, ..., N-1], fully determined by (T, N).
        mod = self.compile("""
            from _simd import SIMD

            def get_i32(i: i32) -> i32:
                v = SIMD[i32, 4].iota()
                return v[i]

            def get_f32(i: i32) -> f32:
                v = SIMD[f32, 4].iota()
                return v[i]
            """)
        for i in range(4):
            assert mod.get_i32(i) == i
            assert mod.get_f32(i) == float(i)

    def test_iota_all_dtypes(self):
        # every v1 numeric primitive can be used as the lane dtype
        mod = self.compile("""
            from _simd import SIMD

            def last[T]() -> T:
                v = SIMD[T, 4].iota()
                return v[3]

            last_i8 = last[i8]
            last_u8 = last[u8]
            last_i32 = last[i32]
            last_u32 = last[u32]
            last_i64 = last[i64]
            last_u64 = last[u64]
            last_f32 = last[f32]
            last_f64 = last[f64]
            """)
        assert mod.last_i8() == 3
        assert mod.last_u8() == 3
        assert mod.last_i32() == 3
        assert mod.last_u32() == 3
        assert mod.last_i64() == 3
        assert mod.last_u64() == 3
        assert mod.last_f32() == 3.0
        assert mod.last_f64() == 3.0

    def test_iota_sizes(self):
        # size must be a positive power of two: 1, 2, 4, 8 are all valid,
        # same as construction (test_valid_sizes).
        mod = self.compile("""
            from _simd import SIMD

            def s1() -> i32:
                v = SIMD[i32, 1].iota()
                return v[0]

            def s2() -> i32:
                v = SIMD[i32, 2].iota()
                return v[1]

            def s8() -> i32:
                v = SIMD[i32, 8].iota()
                return v[7]
            """)
        assert mod.s1() == 0
        assert mod.s2() == 1
        assert mod.s8() == 7

    def test_iota_reduce_add(self):
        # iota() composes with other SIMD operations like any other vector.
        mod = self.compile("""
            from _simd import SIMD

            def sum_iota() -> i32:
                v = SIMD[i32, 4].iota()  # [0, 1, 2, 3]
                return v.reduce_add()
            """)
        assert mod.sum_iota() == 6  # 0+1+2+3

    def test_invalid_size_not_power_of_two(self):
        src = """
        from _simd import SIMD

        def bad() -> None:
            v = SIMD[f32, 3](1.0)
        """
        errors = expect_errors("SIMD size must be a power of two, got 3")
        self.compile_raises(src, "bad", errors)

    def test_invalid_size_zero(self):
        src = """
        from _simd import SIMD

        def bad() -> None:
            v = SIMD[f32, 0](1.0)
        """
        errors = expect_errors("SIMD size must be a positive power of two, got 0")
        self.compile_raises(src, "bad", errors)

    def test_invalid_size_negative(self):
        src = """
        from _simd import SIMD

        def bad() -> None:
            v = SIMD[f32, -2](1.0)
        """
        errors = expect_errors("SIMD size must be a positive power of two, got -2")
        self.compile_raises(src, "bad", errors)

    def test_invalid_dtype_bool(self):
        src = """
        from _simd import SIMD

        def bad() -> None:
            v = SIMD[bool, 4](True)
        """
        errors = expect_errors(
            "SIMD element type must be a numeric primitive, got `bool`"
        )
        self.compile_raises(src, "bad", errors)

    def test_invalid_dtype_str(self):
        src = """
        from _simd import SIMD

        def bad() -> None:
            v = SIMD[str, 4]("")
        """
        errors = expect_errors(
            "SIMD element type must be a numeric primitive, got `str`"
        )
        self.compile_raises(src, "bad", errors)

    def test_invalid_dtype_struct(self):
        src = """
        from _simd import SIMD

        @struct
        class Point:
            x: i32
            y: i32

        def bad() -> None:
            v = SIMD[Point, 4](Point(0, 0))
        """
        errors = expect_errors(
            "SIMD element type must be a numeric primitive, got `test::Point`"
        )
        self.compile_raises(src, "bad", errors)

    # === lane read v[i] (red index, simd.getitem irtag -> C.Index) ===

    def test_per_element_read(self):
        mod = self.compile("""
            from _simd import SIMD

            def get_lane(idx: i32) -> f64:
                v = SIMD[f64, 4](10.0, 20.0, 30.0, 40.0)
                return v[idx]
            """)
        assert mod.get_lane(0) == 10.0
        assert mod.get_lane(1) == 20.0
        assert mod.get_lane(2) == 30.0
        assert mod.get_lane(3) == 40.0

    def test_broadcast_all_lanes_equal(self):
        mod = self.compile("""
            from _simd import SIMD

            def lane(a: f32, i: i32) -> f32:
                v = SIMD[f32, 4](a)
                return v[i]
            """)
        for i in range(4):
            assert mod.lane(1.25, i) == 1.25

    def test_runtime_index_in_loop(self):
        # the index `i` is a red (runtime) value: this is what vector-extension
        # subscripting buys us over `tuple` (which requires blue indices).
        mod = self.compile("""
            from _simd import SIMD

            def sum_lanes(a: i32, b: i32, c: i32, d: i32) -> i32:
                v = SIMD[i32, 4](a, b, c, d)
                s: i32 = 0
                for i in range(4):
                    s = s + v[i]
                return s
            """)
        assert mod.sum_lanes(1, 2, 3, 4) == 10
        assert mod.sum_lanes(10, 20, 30, 40) == 100

    @only_interp
    def test_index_out_of_bounds(self):
        # the interpreter bounds-checks lane access; the C backend lowers
        # v[i] to a raw vector-extension subscript (no bounds check), so this
        # panic is interp-only. W_PanicError matches the ptr.getitem convention
        # (see unsafe/ptr.py::w_GETITEM).
        mod = self.compile("""
            from _simd import SIMD

            def bad(i: i32) -> f32:
                v = SIMD[f32, 4](1.0)
                return v[i]
            """)
        with SPyError.raises("W_PanicError", match="SIMD index out of bounds"):
            mod.bad(4)
        with SPyError.raises("W_PanicError", match="SIMD index out of bounds"):
            mod.bad(-1)

    # === whole-vector load/store through gc_ptr[SIMD[...]] ===

    def test_store_load_whole_vector(self):
        mod = self.compile("""
            from unsafe import gc_alloc, gc_ptr
            from _simd import SIMD

            def roundtrip(a: f32, b: f32, c: f32, d: f32) -> f32:
                p: gc_ptr[SIMD[f32, 4]] = gc_alloc[SIMD[f32, 4]](1)
                p[0] = SIMD[f32, 4](a, b, c, d)
                v = p[0]
                return v[2]
            """)
        assert mod.roundtrip(1.0, 2.0, 3.0, 4.0) == 3.0

    def test_store_load_multiple_vectors(self):
        mod = self.compile("""
            from unsafe import gc_alloc, gc_ptr
            from _simd import SIMD

            def total() -> i32:
                p: gc_ptr[SIMD[i32, 2]] = gc_alloc[SIMD[i32, 2]](3)
                p[0] = SIMD[i32, 2](1, 2)
                p[1] = SIMD[i32, 2](3, 4)
                p[2] = SIMD[i32, 2](5, 6)
                s: i32 = 0
                for i in range(3):
                    v = p[i]
                    s = s + v[0] + v[1]
                return s
            """)
        assert mod.total() == 21

    def test_overwrite_slot(self):
        mod = self.compile("""
            from unsafe import gc_alloc, gc_ptr
            from _simd import SIMD

            def overwrite() -> f32:
                p: gc_ptr[SIMD[f32, 2]] = gc_alloc[SIMD[f32, 2]](1)
                p[0] = SIMD[f32, 2](1.0, 2.0)
                p[0] = SIMD[f32, 2](3.0, 4.0)
                v = p[0]
                return v[1]
            """)
        assert mod.overwrite() == 4.0

    def test_roundtrip_all_dtypes(self):
        # one vector of each v1 dtype survives a store/load round-trip
        mod = self.compile("""
            from unsafe import gc_alloc, gc_ptr
            from _simd import SIMD

            def rt_i8(x: i32) -> i8:
                p: gc_ptr[SIMD[i8, 4]] = gc_alloc[SIMD[i8, 4]](1)
                p[0] = SIMD[i8, 4](i8(x), i8(x), i8(x), i8(x))
                return p[0][0]

            def rt_u8(x: i32) -> u8:
                p: gc_ptr[SIMD[u8, 4]] = gc_alloc[SIMD[u8, 4]](1)
                p[0] = SIMD[u8, 4](u8(x), u8(x), u8(x), u8(x))
                return p[0][0]

            def rt_i32(x: i32) -> i32:
                p: gc_ptr[SIMD[i32, 4]] = gc_alloc[SIMD[i32, 4]](1)
                p[0] = SIMD[i32, 4](x, x, x, x)
                return p[0][0]

            def rt_u32(x: i32) -> u32:
                p: gc_ptr[SIMD[u32, 4]] = gc_alloc[SIMD[u32, 4]](1)
                p[0] = SIMD[u32, 4](u32(x), u32(x), u32(x), u32(x))
                return p[0][0]

            def rt_i64(x: i32) -> i64:
                p: gc_ptr[SIMD[i64, 4]] = gc_alloc[SIMD[i64, 4]](1)
                p[0] = SIMD[i64, 4](i64(x), i64(x), i64(x), i64(x))
                return p[0][0]

            def rt_u64(x: i32) -> u64:
                p: gc_ptr[SIMD[u64, 4]] = gc_alloc[SIMD[u64, 4]](1)
                p[0] = SIMD[u64, 4](u64(i64(x)), u64(i64(x)), u64(i64(x)), u64(i64(x)))
                return p[0][0]

            def rt_f32(x: f64) -> f32:
                p: gc_ptr[SIMD[f32, 4]] = gc_alloc[SIMD[f32, 4]](1)
                p[0] = SIMD[f32, 4](f32(x), f32(x), f32(x), f32(x))
                return p[0][0]

            def rt_f64(x: f64) -> f64:
                p: gc_ptr[SIMD[f64, 4]] = gc_alloc[SIMD[f64, 4]](1)
                p[0] = SIMD[f64, 4](x, x, x, x)
                return p[0][0]
            """)
        assert mod.rt_i8(-5) == -5
        assert mod.rt_u8(200) == 200
        assert mod.rt_i32(42) == 42
        assert mod.rt_u32(42) == 42
        assert mod.rt_i64(42) == 42
        assert mod.rt_u64(42) == 42
        assert mod.rt_f32(1.5) == 1.5
        assert mod.rt_f64(2.25) == 2.25

    # === value semantics: immutable bare value, by-value pass/return ===

    def test_bare_setitem_rejected(self):
        # §4.5: no SIMD.__setitem__ on a bare value, only __getitem__.
        # simd.setitem (lane write) is postponed to a later PR, so a bare
        # `v[i] = x` is simply not supported.
        src = """
        from _simd import SIMD

        def bad() -> None:
            v = SIMD[i32, 4](1, 2, 3, 4)
            v[0] = 99
        """
        errors = expect_errors(
            "type `SIMD[i32, 4]` does not support item assignment",
            ("this is `SIMD[i32, 4]`", "v"),
        )
        self.compile_raises(src, "bad", errors)

    def test_pass_and_return_by_value(self):
        # SIMD passed/returned by value between SPy functions. The exported
        # `entry` returns a scalar, so no SIMD value crosses the WASM/Python
        # boundary and this runs on all backends.
        mod = self.compile("""
            from _simd import SIMD

            def identity(v: SIMD[f32, 4]) -> SIMD[f32, 4]:
                return v

            def first_lane(v: SIMD[f32, 4]) -> f32:
                return v[0]

            def entry() -> f32:
                v = SIMD[f32, 4](1.0, 2.0, 3.0, 4.0)
                w = identity(v)
                a = first_lane(v)
                # w is a by-value copy: reads back the same lanes
                return w[2] + a
            """)
        assert mod.entry() == 4.0  # w[2] (3.0) + first_lane(v) (1.0)

    # === elementwise arithmetic: simd.binop ===

    def test_binop_add_sub_mul_i32(self):
        mod = self.compile("""
            from _simd import SIMD

            def add0(a: i32, b: i32) -> i32:
                v = SIMD[i32, 4](a, a, a, a)
                w = SIMD[i32, 4](b, b, b, b)
                return (v + w)[0]

            def sub0(a: i32, b: i32) -> i32:
                v = SIMD[i32, 4](a, a, a, a)
                w = SIMD[i32, 4](b, b, b, b)
                return (v - w)[0]

            def mul0(a: i32, b: i32) -> i32:
                v = SIMD[i32, 4](a, a, a, a)
                w = SIMD[i32, 4](b, b, b, b)
                return (v * w)[0]
            """)
        assert mod.add0(3, 4) == 7
        assert mod.sub0(10, 4) == 6
        assert mod.mul0(3, 4) == 12

    def test_binop_wraparound(self):
        # SIMD integer arithmetic follows C wraparound
        mod = self.compile("""
            from _simd import SIMD

            def add_u8(a: i32) -> u8:
                v = SIMD[u8, 4](u8(a))
                return (v + v)[0]

            def mul_i8(a: i32) -> i8:
                v = SIMD[i8, 4](i8(a))
                w = SIMD[i8, 4](3)
                return (v * w)[0]
            """)
        assert mod.add_u8(200) == 144  # 400 mod 256
        assert mod.mul_i8(100) == 44  # 300 mod 256 = 44, as signed i8

    def test_binop_add_all_dtypes(self):
        mod = self.compile("""
            from _simd import SIMD

            def f_i8(a: i32) -> i8:
                v = SIMD[i8, 4](i8(a))
                return (v + v)[0]

            def f_u8(a: i32) -> u8:
                v = SIMD[u8, 4](u8(a))
                return (v + v)[0]

            def f_i32(a: i32) -> i32:
                v = SIMD[i32, 4](a)
                return (v + v)[0]

            def f_u32(a: i32) -> u32:
                v = SIMD[u32, 4](u32(a))
                return (v + v)[0]

            def f_i64(a: i32) -> i64:
                v = SIMD[i64, 4](i64(a))
                return (v + v)[0]

            def f_u64(a: i32) -> u64:
                v = SIMD[u64, 4](u64(i64(a)))
                return (v + v)[0]

            def f_f32(a: f64) -> f32:
                v = SIMD[f32, 4](f32(a))
                return (v + v)[0]

            def f_f64(a: f64) -> f64:
                v = SIMD[f64, 4](a)
                return (v + v)[0]
            """)
        assert mod.f_i8(5) == 10
        assert mod.f_u8(100) == 200
        assert mod.f_i32(42) == 84
        assert mod.f_u32(42) == 84
        assert mod.f_i64(42) == 84
        assert mod.f_u64(42) == 84
        assert mod.f_f32(1.5) == 3.0
        assert mod.f_f64(2.25) == 4.5

    def test_binop_float_div(self):
        mod = self.compile("""
            from _simd import SIMD

            def div_f32(a: f32, b: f32) -> f32:
                v = SIMD[f32, 4](a, a, a, a)
                w = SIMD[f32, 4](b, b, b, b)
                return (v / w)[0]

            def div_f64(a: f64, b: f64) -> f64:
                v = SIMD[f64, 4](a, a, a, a)
                w = SIMD[f64, 4](b, b, b, b)
                return (v / w)[0]
            """)
        assert mod.div_f32(1.0, 4.0) == 0.25
        assert mod.div_f64(1.0, 8.0) == 0.125

    def test_binop_int_div_error(self):
        # integer `/` is deferred in v1 -> NULL -> standard type error.
        src = """
        from _simd import SIMD

        def bad() -> None:
            v = SIMD[i32, 4](1, 2, 3, 4)
            w = SIMD[i32, 4](2, 2, 2, 2)
            x = v / w
        """
        errors = expect_errors("cannot do `SIMD[i32, 4]` / `SIMD[i32, 4]`")
        self.compile_raises(src, "bad", errors)

    def test_binop_per_lane(self):
        mod = self.compile("""
            from _simd import SIMD

            def add0() -> i32:
                v = SIMD[i32, 4](1, 2, 3, 4)
                w = SIMD[i32, 4](10, 20, 30, 40)
                r = v + w
                s: i32 = 0
                for i in range(4):
                    s = s + r[i]
                return s
            """)
        assert mod.add0() == 110  # 11 + 22 + 33 + 44

    # === elementwise comparison: simd.cmp ===

    def test_cmp_i32(self):
        mod = self.compile("""
            from _simd import SIMD

            def lt(a: i32, b: i32) -> i32:
                v = SIMD[i32, 4](a, a, a, a)
                w = SIMD[i32, 4](b, b, b, b)
                return (v < w)[0]

            def eq(a: i32, b: i32) -> i32:
                v = SIMD[i32, 4](a, a, a, a)
                w = SIMD[i32, 4](b, b, b, b)
                return (v == w)[0]

            def ge(a: i32, b: i32) -> i32:
                v = SIMD[i32, 4](a, a, a, a)
                w = SIMD[i32, 4](b, b, b, b)
                return (v >= w)[0]
            """)
        # mask lanes are -1 (true, all-ones) / 0 (false), as signed i32.
        assert mod.lt(3, 5) == -1
        assert mod.lt(5, 3) == 0
        assert mod.lt(3, 3) == 0
        assert mod.eq(3, 3) == -1
        assert mod.eq(3, 4) == 0
        assert mod.ge(3, 3) == -1
        assert mod.ge(2, 3) == 0

    def test_cmp_mask_dtype_is_signed_int(self):
        # f32 comparison yields a SIMD[i32, 4] mask; u8 yields SIMD[i8, 4].
        mod = self.compile("""
            from _simd import SIMD

            def cmp_f32(a: f32, b: f32) -> i32:
                v = SIMD[f32, 4](a, a, a, a)
                w = SIMD[f32, 4](b, b, b, b)
                return (v < w)[0]

            def cmp_u8(a: i32, b: i32) -> i8:
                v = SIMD[u8, 4](u8(a))
                w = SIMD[u8, 4](u8(b))
                return (v < w)[0]
            """)
        assert mod.cmp_f32(1.0, 2.0) == -1
        assert mod.cmp_f32(2.0, 1.0) == 0
        assert mod.cmp_u8(1, 2) == -1
        assert mod.cmp_u8(2, 1) == 0

    def test_cmp_per_lane(self):
        mod = self.compile("""
            from _simd import SIMD

            def f() -> i32:
                v = SIMD[i32, 4](1, 5, 3, 7)
                w = SIMD[i32, 4](2, 4, 3, 0)
                m = v < w   # T, F, F, F
                s: i32 = 0
                for i in range(4):
                    s = s + m[i]
                return s
            """)
        assert mod.f() == -1  # only lane 0 is true -> one -1

    # === mask.select(a, b): simd.select ===

    def test_select_cmp_mask(self):
        mod = self.compile("""
            from _simd import SIMD

            def sel(a: f32, b: f32) -> f32:
                v = SIMD[f32, 4](a, a, a, a)
                w = SIMD[f32, 4](b, b, b, b)
                m = v < w
                r = m.select(v, w)
                return r[0]
            """)
        # a < b => mask true => select picks the first arg (v = a)
        assert mod.sel(1.0, 2.0) == 1.0
        # a > b => mask false => picks the second arg (w = b)
        assert mod.sel(3.0, 2.0) == 2.0
        # a == b => mask false => picks b
        assert mod.sel(2.0, 2.0) == 2.0

    def test_select_per_lane(self):
        mod = self.compile("""
            from _simd import SIMD

            def sel(idx: i32) -> f32:
                v = SIMD[f32, 4](10.0, 20.0, 30.0, 40.0)
                w = SIMD[f32, 4](1.0, 2.0, 3.0, 4.0)
                m = SIMD[i32, 4](-1, 0, -1, 0)
                r = m.select(v, w)
                return r[idx]
            """)
        # canonical mask lanes (-1 picks v, 0 picks w): interp == C.
        assert mod.sel(0) == 10.0
        assert mod.sel(1) == 2.0
        assert mod.sel(2) == 30.0
        assert mod.sel(3) == 4.0

    def test_select_max(self):
        # classic blend idiom: per-lane max via (a > b).select(a, b).
        mod = self.compile("""
            from _simd import SIMD

            def vmax0(a: f32, b: f32) -> f32:
                v = SIMD[f32, 4](a, a, a, a)
                w = SIMD[f32, 4](b, b, b, b)
                m = v > w
                r = m.select(v, w)
                return r[0]

            def vmax_all() -> f32:
                v = SIMD[f32, 4](10.0, 2.0, 30.0, 4.0)
                w = SIMD[f32, 4](5.0, 8.0, 1.0, 9.0)
                m = v > w
                r = m.select(v, w)
                s: f32 = 0.0
                for i in range(4):
                    s = s + r[i]
                return s
            """)
        assert mod.vmax0(1.0, 2.0) == 2.0
        assert mod.vmax0(5.0, 2.0) == 5.0
        assert mod.vmax_all() == 57.0  # 10 + 8 + 30 + 9

    def test_select_wrong_mask_size_error(self):
        # a mask whose size does not match the operand is not a valid select.
        src = """
        from _simd import SIMD

        def bad() -> None:
            v = SIMD[f32, 4](1.0)
            w = SIMD[f32, 4](2.0)
            m = SIMD[i32, 2](-1, 0)
            r = m.select(v, w)
        """
        errors = expect_errors("method `SIMD[i32, 2]::select` does not exist")
        self.compile_raises(src, "bad", errors)

    # === simd.reduce ===

    def test_reduce_add_all_dtypes(self):
        mod = self.compile("""
            from _simd import SIMD

            def r[T](a: T) -> T:
                v = SIMD[T, 4](a, a, a, a)
                return v.reduce_add()

            r_i8 = r[i8]
            r_u8 = r[u8]
            r_i32 = r[i32]
            r_u32 = r[u32]
            r_f32 = r[f32]
            r_i64 = r[i64]
            r_u64 = r[u64]
            r_f64 = r[f64]
            """)
        assert mod.r_i8(5) == 20
        assert mod.r_u8(10) == 40
        assert mod.r_i32(-42) == -168
        assert mod.r_u32(42) == 168
        assert mod.r_f32(2.0) == 8.0
        assert mod.r_i64(-42) == -168
        assert mod.r_u64(42) == 168
        assert mod.r_f64(2.0) == 8.0

    def test_reduce_add_wraparound(self):
        # reduce_add wraps in the lane type
        mod = self.compile("""
            from _simd import SIMD

            def r[T](a: T) -> T:
                v = SIMD[T, 4](a, a, a, a)
                return v.reduce_add()

            r_i8 = r[i8]
            r_u8 = r[u8]
            """)
        # 100 * 4 = 400; 400 mod 256 = 144, interpreted as signed i8 = 144 - 256 = -112
        assert mod.r_i8(100) == -112
        # 200 * 4 = 800; 800 mod 256 = 32
        assert mod.r_u8(200) == 32

    def test_reduce_add_size1(self):
        # a single-lane vector reduces to its lane value
        mod = self.compile("""
            from _simd import SIMD

            def r(x: f32) -> f32:
                v = SIMD[f32, 1](x)
                return v.reduce_add()
            """)
        assert mod.r(7.5) == 7.5

    def test_reduce_add_dot_product(self):
        # the motivating use case: replace the manual scalar tail loop in
        # dot_simd with a single horizontal reduce_add.
        mod = self.compile("""
            from _simd import SIMD

            def dot(x0: f32, x1: f32, x2: f32, x3: f32,
                    y0: f32, y1: f32, y2: f32, y3: f32) -> f32:
                vx = SIMD[f32, 4](x0, x1, x2, x3)
                vy = SIMD[f32, 4](y0, y1, y2, y3)
                acc = vx * vy
                return acc.reduce_add()
            """)
        assert mod.dot(1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0) == 70.0

    def test_reduce_all_operations_together(self):
        mod = self.compile("""
            from _simd import SIMD

            def all_reductions[T]() -> tuple[T, T, T, T]:
                v = SIMD[T, 4](1, 2, 3, 4)
                return (v.reduce_add(), v.reduce_min(), v.reduce_max(), v.reduce_mul())

            all_reductions_i8 = all_reductions[i8]
            all_reductions_i32 = all_reductions[i32]
            all_reductions_f32 = all_reductions[f32]
            all_reductions_f64 = all_reductions[f64]
            """)
        # sum=10, min=1, max=4, product=24
        correct_f = (10.0, 1.0, 4.0, 24.0)
        correct_i = (10, 1, 4, 24)
        assert _as_tuple(mod.all_reductions_i8()) == correct_i
        assert _as_tuple(mod.all_reductions_i32()) == correct_i
        assert _as_tuple(mod.all_reductions_f32()) == correct_f
        assert _as_tuple(mod.all_reductions_f64()) == correct_f

    # === simd.reinterpret: reinterpret_as ===

    def test_reinterpret_as_same_bytes(self):
        # reinterpret bits between same-byte-width lanes: f32 <-> i32
        mod = self.compile("""
            from _simd import SIMD, reinterpret_as

            def f2i(v0: f32, v1: f32, v2: f32, v3: f32) -> i32:
                v = SIMD[f32, 4](v0, v1, v2, v3)
                w = reinterpret_as(v, i32)
                return w[0]

            def i2f(v0: i32, v1: i32, v2: i32, v3: i32) -> f32:
                v = SIMD[i32, 4](v0, v1, v2, v3)
                w = reinterpret_as(v, f32)
                return w[0]
            """)
        # 1.0 as f32 has bit pattern 0x3F800000 == 1065353216
        assert mod.f2i(1.0, 2.0, 3.0, 4.0) == 1065353216
        # 1065353216 as i32 reinterpreted to f32 is 1.0
        assert mod.i2f(1065353216, 0, 0, 0) == 1.0

    def test_reinterpret_as_identity(self):
        # reinterpreting to the same dtype is a no-op (bits unchanged)
        mod = self.compile("""
            from _simd import SIMD, reinterpret_as

            def r(v0: i32, v1: i32, v2: i32, v3: i32) -> i32:
                v = SIMD[i32, 4](v0, v1, v2, v3)
                w = reinterpret_as(v, i32)
                return w[1]
            """)
        assert mod.r(10, 20, 30, 40) == 20

    def test_reinterpret_as_i8_u8(self):
        mod = self.compile("""
            from _simd import SIMD, reinterpret_as

            def to_u8(v0: i8, v1: i8) -> u8:
                v = SIMD[i8, 2](v0, v1)
                w = reinterpret_as(v, u8)
                return w[0]

            def to_i8(v0: u8, v1: u8) -> i8:
                v = SIMD[u8, 2](v0, v1)
                w = reinterpret_as(v, i8)
                return w[0]
            """)
        # -1 as i8 is 0xFF, which as u8 is 255
        assert mod.to_u8(-1, 0) == 255
        # 255 as u8 is 0xFF, which as i8 is -1
        assert mod.to_i8(255, 0) == -1

    def test_reinterpret_as_width_mismatch_error(self):
        src = """
        from _simd import SIMD, reinterpret_as

        def bad() -> None:
            v = SIMD[f32, 4](1.0)
            w = reinterpret_as(v, i64)
        """
        errors = expect_errors(
            "cannot reinterpret `SIMD[f32, 4]` as `SIMD[i64, 4]`: lane byte-width mismatch"
        )
        self.compile_raises(src, "bad", errors)

    def test_reinterpret_as_non_simd_error(self):
        src = """
        from _simd import reinterpret_as

        def bad() -> None:
            var x: f32 = 2.0
            w = reinterpret_as(x, i32)
        """
        errors = expect_errors("mismatched types")
        self.compile_raises(src, "bad", errors)

    def test_reinterpret_as_ldexp_trick(self):
        # the motivating use case: build 2^k by reinterpreting an int vector
        # as a float vector (k + 127 in the exponent field, mantissa 0).
        mod = self.compile("""
            from _simd import SIMD, reinterpret_as

            def two_pow_k(k0: i32, k1: i32) -> f32:
                # float32(2^k) bit pattern = (k + 127) << 23
                e0 = (k0 + 127) << 23
                e1 = (k1 + 127) << 23
                vi = SIMD[i32, 2](e0, e1)
                vf = reinterpret_as(vi, f32)
                return vf[0]
            """)
        assert mod.two_pow_k(0, 1) == 1.0  # 2^0
        assert mod.two_pow_k(1, 0) == 2.0  # 2^1
        assert mod.two_pow_k(2, 0) == 4.0  # 2^2

    # === simd.round: floor / trunc / round / ceil ===

    def test_round_floor(self):
        mod = self.compile("""
            from _simd import SIMD

            def r[T](x: T) -> tuple[T, T, T, T]:
                v = SIMD[T, 4](x, -x, x + 0.5, -x - 0.5)
                f = v.floor()
                return f[0], f[1], f[2], f[3]

            floor_f32 = r[f32]
            floor_f64 = r[f64]
            """)
        # floor: toward -inf.
        assert _as_tuple(mod.floor_f32(1.7)) == (1.0, -2.0, 2.0, -3.0)
        assert _as_tuple(mod.floor_f64(1.7)) == (1.0, -2.0, 2.0, -3.0)

    def test_round_trunc(self):
        mod = self.compile("""
            from _simd import SIMD

            def trunc[T](x: T) -> tuple[T, T]:
                v = SIMD[T, 2](x, -x)
                t = v.trunc()
                return t[0], t[1]

            trunc_f32 = trunc[f32]
            trunc_f64 = trunc[f64]
            """)
        # trunc: toward zero. trunc(1.9)=1, trunc(-1.9)=-1
        assert _as_tuple(mod.trunc_f32(1.9)) == (1.0, -1.0)
        assert _as_tuple(mod.trunc_f64(1.9)) == (1.0, -1.0)

    def test_round_ceil(self):
        mod = self.compile("""
            from _simd import SIMD

            def ceil[T](x: T) -> tuple[T, T]:
                v = SIMD[T, 2](x, -x)
                c = v.ceil()
                return c[0], c[1]

            ceil_f32 = ceil[f32]
            ceil_f64 = ceil[f64]
            """)
        # ceil: toward +inf. ceil(1.1)=2, ceil(-1.1)=-1
        assert _as_tuple(mod.ceil_f32(1.1)) == (2.0, -1.0)
        assert _as_tuple(mod.ceil_f64(1.1)) == (2.0, -1.0)

    def test_round_half_to_even_all_lanes(self):
        mod = self.compile("""
            from _simd import SIMD

            def round() -> tuple[f64, f64, f64, f64]:
                s = SIMD[f64, 4](0.5, 1.5, 2.5, 3.5).round()
                return s[0], s[1], s[2], s[3]
            """)
        assert _as_tuple(mod.round()) == (0.0, 2.0, 2.0, 4.0)

    def test_round_integer_rejected(self):
        # floor/trunc/round/ceil are float-only: integer lanes are rejected.
        src = """
        from _simd import SIMD

        def bad() -> None:
            v = SIMD[i32, 4](1, 2, 3, 4)
            return v.floor()
        """
        errors = expect_errors("method `SIMD[i32, 4]::floor` does not exist")
        self.compile_raises(src, "bad", errors)

    def test_round_argument_reduction(self):
        # the motivating use case: k = floor(x / ln2) for exp argument reduction.
        mod = self.compile("""
            from _simd import SIMD

            def k_floor(x0: f32, x1: f32) -> i32:
                # x / ln2, rounded down to the exponent k
                ln2: f32 = 0.6931471805599453
                vx = SIMD[f32, 2](x0, x1)
                vk = (vx / SIMD[f32, 2](ln2)).floor()
                return i32(vk[0])
            """)
        # floor(1.0 / ln2) = floor(1.4427) = 1
        assert mod.k_floor(1.0, 0.0) == 1
        # floor(3.0 / ln2) = floor(4.328) = 4
        assert mod.k_floor(3.0, 0.0) == 4

    # === simd.cast: cast_to (numeric lane-wise cast) ===

    def test_cast_to_f32_i32(self):
        mod = self.compile("""
            from _simd import SIMD, cast_to

            def f2i(v0: f32, v1: f32) -> i32:
                v = SIMD[f32, 2](v0, v1)
                w = cast_to(v, i32)
                return w[0]

            def i2f(v0: i32, v1: i32) -> f32:
                v = SIMD[i32, 2](v0, v1)
                w = cast_to(v, f32)
                return w[0]
        """)
        # numeric (not bit) conversion: 1.0 -> 1, not 1065353216
        assert mod.f2i(1.0, 2.0) == 1
        assert mod.f2i(3.7, 0.0) == 3  # truncation towards zero
        assert mod.f2i(-2.9, 0.0) == -2
        assert mod.i2f(5, 0) == 5.0
        assert mod.i2f(-3, 0) == -3.0

    def test_cast_to_all_pairs(self):
        mod = self.compile("""
            from _simd import SIMD, cast_to

            def f64_i64(v0: f64, v1: f64) -> i64:
                v = SIMD[f64, 2](v0, v1)
                w = cast_to(v, i64)
                return w[0]

            def i64_f64(v0: i64, v1: i64) -> f64:
                v = SIMD[i64, 2](v0, v1)
                w = cast_to(v, f64)
                return w[0]

            def i32_u32(v0: i32, v1: i32) -> u32:
                v = SIMD[i32, 2](v0, v1)
                w = cast_to(v, u32)
                return w[0]
        """)
        assert mod.f64_i64(2.7, 0.0) == 2
        assert mod.i64_f64(42, 0) == 42.0
        # -1 as i32 is 0xFFFFFFFF, cast to u32 is 4294967295
        assert mod.i32_u32(-1, 0) == 4294967295

    def test_cast_to_vs_reinterpret(self):
        # cast_to does numeric conversion, reinterpret_as does bit copy.
        # 1.0f32: cast_to -> 1, reinterpret_as -> 1065353216 (0x3F800000)
        mod = self.compile("""
            from _simd import SIMD, cast_to, reinterpret_as

            def f2i_cast(v0: f32) -> i32:
                v = SIMD[f32, 1](v0)
                return cast_to(v, i32)[0]

            def f2i_reinterpret(v0: f32) -> i32:
                v = SIMD[f32, 1](v0)
                return reinterpret_as(v, i32)[0]
        """)
        assert mod.f2i_cast(1.0) == 1
        assert mod.f2i_reinterpret(1.0) == 1065353216

    def test_cast_to_width_mismatch_error(self):
        src = """
        from _simd import SIMD, cast_to

        def bad() -> i64:
            v = SIMD[f32, 1](1.0)
            w = cast_to(v, i64)
            return w[0]
        """
        errors = expect_errors(
            "cannot cast `SIMD[f32, 1]` as `SIMD[i64, 1]`: lane byte-width mismatch"
        )
        self.compile_raises(src, "bad", errors)

    # === simd.ldexp: scale float vector by 2^k ===

    def test_ldexp_basic(self):
        mod = self.compile("""
            from _simd import SIMD, ldexp

            def scale(v0: f32, v1: f32, k0: i32, k1: i32) -> f32:
                v = SIMD[f32, 2](v0, v1)
                k = SIMD[i32, 2](k0, k1)
                w = ldexp(v, k)
                return w[0]
        """)
        assert mod.scale(1.0, 1.0, 0, 0) == 1.0
        assert mod.scale(1.0, 1.0, 1, 0) == 2.0
        assert mod.scale(1.0, 1.0, 3, 0) == 8.0
        assert mod.scale(1.5, 1.0, 2, 0) == 6.0
        assert mod.scale(1.0, 1.0, -1, 0) == 0.5

    def test_ldexp_f64(self):
        mod = self.compile("""
            from _simd import SIMD, ldexp

            def scale(v0: f64, v1: f64, k0: i64, k1: i64) -> f64:
                v = SIMD[f64, 2](v0, v1)
                k = SIMD[i64, 2](k0, k1)
                w = ldexp(v, k)
                return w[0]
        """)
        assert mod.scale(1.0, 1.0, 10, 0) == 1024.0
        assert mod.scale(1.0, 1.0, -2, 0) == 0.25

    def test_ldexp_per_lane(self):
        mod = self.compile("""
            from _simd import SIMD, ldexp

            def scale_all(v0: f32, v1: f32, k0: i32, k1: i32) -> tuple[f32, f32]:
                v = SIMD[f32, 2](v0, v1)
                k = SIMD[i32, 2](k0, k1)
                w = ldexp(v, k)
                return (w[0], w[1])
        """)
        t = _as_tuple(mod.scale_all(1.0, 1.0, 1, 3))
        assert t == (2.0, 8.0)
        t = _as_tuple(mod.scale_all(3.0, 5.0, 2, -1))
        assert t == (12.0, 2.5)

    def test_ldexp_int_v_error(self):
        src = """
        from _simd import SIMD, ldexp

        def bad() -> i32:
            v = SIMD[i32, 2](1, 2)
            k = SIMD[i32, 2](3, 4)
            w = ldexp(v, k)
            return w[0]
        """
        errors = expect_errors("v has to be f32 or f64")
        self.compile_raises(src, "bad", errors)

    def test_ldexp_float_k_error(self):
        src = """
        from _simd import SIMD, ldexp

        def bad() -> f32:
            v = SIMD[f32, 2](1.0, 2.0)
            k = SIMD[f32, 2](3.0, 4.0)
            w = ldexp(v, k)
            return w[0]
        """
        errors = expect_errors("k has to be integer")
        self.compile_raises(src, "bad", errors)

    def test_exp_argument_reduction(self):
        # the full motivating use case:
        # k = trunc(x / ln2), r = x - k*ln2, exp(x) = ldexp(exp(r), k)
        # Uses cast_to (truncation, no function call) instead of floor
        # to match the bench's zero-function-call approach.
        mod = self.compile("""
            from _simd import SIMD, ldexp, cast_to

            def get_k_and_scale(x0: f32, x1: f32) -> tuple[i32, f32, f32]:
                ln2: f32 = 0.6931471805599453
                vx = SIMD[f32, 2](x0, x1)
                vk_f = vx / SIMD[f32, 2](ln2)
                vk_i = cast_to(vk_f, i32)
                vk_f = cast_to(vk_i, f32)
                one = SIMD[f32, 2](1.0)
                two_pow_k = ldexp(one, vk_i)
                return (vk_i[0], two_pow_k[0], two_pow_k[1])
        """)
        k0, pow0, pow1 = _as_tuple(mod.get_k_and_scale(1.0, 3.0))
        # trunc(1.0/ln2) = trunc(1.4427) = 1, 2^1 = 2.0
        assert k0 == 1
        assert abs(pow0 - 2.0) < 1e-6
        # trunc(3.0/ln2) = trunc(4.328) = 4, 2^4 = 16.0
        assert abs(pow1 - 16.0) < 1e-6

    # === pointer load/store of whole SIMD vectors ===

    def test_ptr_load_store_roundtrip(self):
        mod = self.compile("""
            from unsafe import gc_alloc, raw_alloc
            from _simd import SIMD, ptr_load_simd, ptr_store_simd

            def roundtrip_gc(a: f32, b: f32, c: f32, d: f32) -> f32:
                p = gc_alloc[f32](8)
                v = SIMD[f32, 4](a, b, c, d)
                ptr_store_simd(p, 0, v)
                w = ptr_load_simd[f32, 4](p, 0)
                return w[2]

            def roundtrip_raw(a: f32, b: f32, c: f32, d: f32) -> f32:
                p = raw_alloc[f32](4)
                ptr_store_simd(p, 0, SIMD[f32, 4](a, b, c, d))
                v = ptr_load_simd[f32, 4](p, 0)
                return v[3]
            """)
        assert mod.roundtrip_gc(1.0, 2.0, 3.0, 4.0) == 3.0
        assert mod.roundtrip_raw(1.0, 2.0, 3.0, 4.0) == 4.0

    def test_ptr_load_store_strided_and_overwrite(self):
        mod = self.compile("""
            from unsafe import gc_alloc
            from _simd import SIMD, ptr_load_simd, ptr_store_simd

            def strided() -> i32:
                p = gc_alloc[i32](8)
                ptr_store_simd(p, 0, SIMD[i32, 4](10, 20, 30, 40))
                ptr_store_simd(p, 4, SIMD[i32, 4](50, 60, 70, 80))
                v0 = ptr_load_simd[i32, 4](p, 0)
                v4 = ptr_load_simd[i32, 4](p, 4)
                return v0[1] + v4[0] + v4[3]

            def overwrite() -> f32:
                p = gc_alloc[f32](4)
                ptr_store_simd(p, 0, SIMD[f32, 4](1.0, 2.0, 3.0, 4.0))
                ptr_store_simd(p, 0, SIMD[f32, 4](5.0, 6.0, 7.0, 8.0))
                v = ptr_load_simd[f32, 4](p, 0)
                return v[1]
            """)
        assert mod.strided() == 150  # 20 + 50 + 80
        assert mod.overwrite() == 6.0

    def test_ptr_load_store_red_index(self):
        mod = self.compile("""
            from unsafe import gc_alloc
            from _simd import SIMD, ptr_load_simd, ptr_store_simd

            def store_at(idx: i32) -> f32:
                p = gc_alloc[f32](8)
                ptr_store_simd(p, idx, SIMD[f32, 4](1.0, 2.0, 3.0, 4.0))
                v = ptr_load_simd[f32, 4](p, idx)
                return v[2]
            """)
        assert mod.store_at(0) == 3.0
        assert mod.store_at(4) == 3.0

    def test_ptr_load_store_all_dtypes(self):
        # one vector of each v1 dtype survives a load/store round-trip.
        # i64/u64 (32 B, natural align 32) exercise the unaligned lowering
        # against a normally-aligned (16 B) gc_alloc buffer.
        mod = self.compile("""
            from unsafe import gc_alloc
            from _simd import SIMD, ptr_load_simd, ptr_store_simd

            def rt[T](x: T) -> T:
                p = gc_alloc[T](4)
                ptr_store_simd(p, 0, SIMD[T, 4](x, x, x, x))
                return ptr_load_simd[T, 4](p, 0)[0]

            rt_i8 = rt[i8]
            rt_u8 = rt[u8]
            rt_i32 = rt[i32]
            rt_u32 = rt[u32]
            rt_i64 = rt[i64]
            rt_u64 = rt[u64]
            rt_f32 = rt[f32]
            rt_f64 = rt[f64]
            """)
        assert mod.rt_i8(-5) == -5
        assert mod.rt_u8(200) == 200
        assert mod.rt_i32(42) == 42
        assert mod.rt_u32(42) == 42
        assert mod.rt_i64(42) == 42
        assert mod.rt_u64(42) == 42
        assert mod.rt_f32(1.5) == 1.5
        assert mod.rt_f64(2.25) == 2.25

    def test_saxpy_shape(self):
        mod = self.compile("""
            from unsafe import gc_alloc
            from _simd import SIMD, ptr_load_simd, ptr_store_simd

            load_simd = ptr_load_simd[f32, 4]

            def saxpy(a: f32, n: i32) -> f32:
                x = gc_alloc[f32](n)
                y = gc_alloc[f32](n)
                out = gc_alloc[f32](n)
                for i in range(n):
                    x[i] = 1.0
                    y[i] = 2.0
                va = SIMD[f32, 4](a)
                vx0 = load_simd(x, 0)
                vy0 = load_simd(y, 0)
                ptr_store_simd(out, 0, va * vx0 + vy0)
                vx4 = load_simd(x, 4)
                vy4 = load_simd(y, 4)
                ptr_store_simd(out, 4, va * vx4 + vy4)
                s: f32 = 0.0
                for j in range(n):
                    s = s + out[j]
                return s
            """)
        # out[i] = a*1 + 2 = a+2; a=3.0 -> 5.0 per element, sum = 5*n
        assert mod.saxpy(3.0, 8) == 40.0

    def test_relu_shape(self):
        # load -> compare -> select -> store.
        mod = self.compile("""
            from unsafe import gc_alloc
            from _simd import SIMD, ptr_load_simd, ptr_store_simd

            def relu() -> f32:
                x = gc_alloc[f32](4)
                out = gc_alloc[f32](4)
                x[0] = -1.0
                x[1] = 2.0
                x[2] = -3.0
                x[3] = 4.0
                zero = SIMD[f32, 4](0.0)
                vx = ptr_load_simd[f32, 4](x, 0)
                mask = vx > zero
                r = mask.select(vx, zero)
                ptr_store_simd(out, 0, r)
                s: f32 = 0.0
                for i in range(4):
                    s = s + out[i]
                return s
            """)
        # relu(-1, 2, -3, 4) = (0, 2, 0, 4); sum = 6.0
        assert mod.relu() == 6.0

    def test_ptr_load_invalid_size(self):
        src = """
        from unsafe import gc_alloc
        from _simd import ptr_load_simd

        def bad() -> None:
            p = gc_alloc[f32](4)
            v = ptr_load_simd[f32, 3](p, 0)
        """
        errors = expect_errors("SIMD size must be a power of two, got 3")
        self.compile_raises(src, "bad", errors)

    def test_ptr_load_invalid_dtype(self):
        src = """
        from unsafe import gc_alloc
        from _simd import ptr_load_simd

        def bad() -> None:
            p = gc_alloc[f32](4)
            v = ptr_load_simd[bool, 4](p, 0)
        """
        errors = expect_errors(
            "SIMD element type must be a numeric primitive, got `bool`"
        )
        self.compile_raises(src, "bad", errors)

    def test_ptr_store_non_simd_value(self):
        src = """
        from unsafe import gc_alloc
        from _simd import ptr_store_simd

        def bad() -> None:
            p = gc_alloc[f32](4)
            ptr_store_simd(p, 0, 1.0)
        """
        errors = expect_errors(
            "mismatched types",
            ("expected a SIMD value, got `f64`", "1.0"),
        )
        self.compile_raises(src, "bad", errors)

    # === simd_width_of ===

    def test_simd_width_of_default(self):
        # Default with no --simd-width
        mod = self.compile("""
            from _simd import simd_width_of

            def w() -> i32:
                return simd_width_of[f32]
            """)
        assert mod.w() == 4

    def test_simd_width_of_sizes_simd(self):
        mod = self.compile("""
            from unsafe import gc_alloc
            from _simd import SIMD, ptr_load_simd, ptr_store_simd, simd_width_of

            def lanes() -> i32:
                return simd_width_of[f32]

            def lane(x: f32) -> f32:
                W = simd_width_of[f32]
                v = SIMD[f32, W](x)
                return v[0]
            """)
        assert mod.lanes() == 4
        assert mod.lane(1.5) == 1.5

    def test_simd_width_of_override(self):
        # The build CLI sets vm.simd_width from --simd-width before redshift.
        self.vm.simd_width = 32
        mod = self.compile("""
            from _simd import simd_width_of

            def w() -> i32:
                return simd_width_of[f32]
            """)
        assert mod.w() == 8

    def test_simd_width_of_invalid_dtype(self):
        src = """
        from _simd import simd_width_of

        def bad() -> i32:
            return simd_width_of[bool]
        """
        errors = expect_errors(
            "SIMD element type must be a numeric primitive, got `bool`"
        )
        self.compile_raises(src, "bad", errors)

    def test_sqrt_basic(self):
        mod = self.compile("""
            from _simd import SIMD, sqrt

            def test_sqrt_f32(x: f32) -> f32:
                v = SIMD[f32, 4](x, x, x, x)
                w = sqrt(v)
                return w[0]
            """)
        assert mod.test_sqrt_f32(4.0) == 2.0
        assert mod.test_sqrt_f32(9.0) == 3.0

    def test_sqrt_integer_rejected(self):
        src = """
        from _simd import SIMD, sqrt
        def bad() -> None:
            v = SIMD[i32, 4](1, 2, 3, 4)
            w = sqrt(v)
        """
        errors = expect_errors("sqrt requires float vector, got `_simd::SIMD[i32, 4]`")
        self.compile_raises(src, "bad", errors)

    def test_any_all(self):
        mod = self.compile("""
            from _simd import SIMD, any, all

            def func() -> tuple[bool, bool]:
                v = SIMD[f32, 4](1.0, 0.0, 3.0, 0.0)
                mask = v > SIMD[f32, 4](0.0)
                return any(mask), all(mask)
            """)
        assert _as_tuple(mod.func()) == (True, False)


def test_simd_width_resolution():
    # The default is the universally-safe width for every target.
    for target in SIMD_ALLOWED_WIDTHS:
        assert resolve_simd_width(target, None) == SIMD_DEFAULT_WIDTH
    # native accepts 16/32/64.
    assert resolve_simd_width("native", 16) == 16
    assert resolve_simd_width("native", 32) == 32
    assert resolve_simd_width("native", 64) == 64
    # wasm targets are fixed at 16.
    assert resolve_simd_width("wasi", 16) == 16
    assert resolve_simd_width("emscripten", 16) == 16
    # Non-power-of-two / out-of-range widths are rejected.
    with pytest.raises(ValueError):
        resolve_simd_width("native", 62)
    with pytest.raises(ValueError):
        resolve_simd_width("native", 300)
    # 32/64 are not valid for wasm targets.
    with pytest.raises(ValueError):
        resolve_simd_width("wasi", 32)
    with pytest.raises(ValueError):
        resolve_simd_width("emscripten", 64)
