from spy.errors import SPyError
from spy.tests.support import CompilerTest, expect_errors, only_interp


class TestSIMD(CompilerTest):
    # === construction & validation (blue-time) ===

    def test_valid_sizes(self):
        # size must be a positive power of two: 1, 2, 4, 8 are all valid.
        mod = self.compile(
            """
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
            """
        )
        assert mod.s1(1.5) == 1.5
        assert mod.s2(2.5) == 2.5
        assert mod.s4(3.5) == 3.5
        assert mod.s8(7) == 7

    def test_all_dtypes(self):
        # every v1 numeric primitive can be used as the lane dtype
        mod = self.compile(
            """
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
            """
        )
        assert mod.f_i8(-5) == -5
        assert mod.f_u8(200) == 200
        assert mod.f_i32(42) == 42
        assert mod.f_u32(42) == 42
        assert mod.f_i64(42) == 42
        assert mod.f_u64(42) == 42
        assert mod.f_f32(1.5) == 1.5
        assert mod.f_f64(2.25) == 2.25

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
        mod = self.compile(
            """
            from _simd import SIMD

            def get_lane(idx: i32) -> f64:
                v = SIMD[f64, 4](10.0, 20.0, 30.0, 40.0)
                return v[idx]
            """
        )
        assert mod.get_lane(0) == 10.0
        assert mod.get_lane(1) == 20.0
        assert mod.get_lane(2) == 30.0
        assert mod.get_lane(3) == 40.0

    def test_broadcast_all_lanes_equal(self):
        mod = self.compile(
            """
            from _simd import SIMD

            def lane(a: f32, i: i32) -> f32:
                v = SIMD[f32, 4](a)
                return v[i]
            """
        )
        for i in range(4):
            assert mod.lane(1.25, i) == 1.25

    def test_runtime_index_in_loop(self):
        # the index `i` is a red (runtime) value: this is what vector-extension
        # subscripting buys us over `tuple` (which requires blue indices).
        mod = self.compile(
            """
            from _simd import SIMD

            def sum_lanes(a: i32, b: i32, c: i32, d: i32) -> i32:
                v = SIMD[i32, 4](a, b, c, d)
                s: i32 = 0
                for i in range(4):
                    s = s + v[i]
                return s
            """
        )
        assert mod.sum_lanes(1, 2, 3, 4) == 10
        assert mod.sum_lanes(10, 20, 30, 40) == 100

    @only_interp
    def test_index_out_of_bounds(self):
        # the interpreter bounds-checks lane access; the C backend lowers
        # v[i] to a raw vector-extension subscript (no bounds check), so this
        # panic is interp-only. W_PanicError matches the ptr.getitem convention
        # (see unsafe/ptr.py::w_GETITEM).
        mod = self.compile(
            """
            from _simd import SIMD

            def bad(i: i32) -> f32:
                v = SIMD[f32, 4](1.0)
                return v[i]
            """
        )
        with SPyError.raises("W_PanicError", match="SIMD index out of bounds"):
            mod.bad(4)
        with SPyError.raises("W_PanicError", match="SIMD index out of bounds"):
            mod.bad(-1)

    # === whole-vector load/store through gc_ptr[SIMD[...]] ===

    def test_store_load_whole_vector(self):
        mod = self.compile(
            """
            from unsafe import gc_alloc, gc_ptr
            from _simd import SIMD

            def roundtrip(a: f32, b: f32, c: f32, d: f32) -> f32:
                p: gc_ptr[SIMD[f32, 4]] = gc_alloc[SIMD[f32, 4]](1)
                p[0] = SIMD[f32, 4](a, b, c, d)
                v = p[0]
                return v[2]
            """
        )
        assert mod.roundtrip(1.0, 2.0, 3.0, 4.0) == 3.0

    def test_store_load_multiple_vectors(self):
        mod = self.compile(
            """
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
            """
        )
        assert mod.total() == 21

    def test_overwrite_slot(self):
        mod = self.compile(
            """
            from unsafe import gc_alloc, gc_ptr
            from _simd import SIMD

            def overwrite() -> f32:
                p: gc_ptr[SIMD[f32, 2]] = gc_alloc[SIMD[f32, 2]](1)
                p[0] = SIMD[f32, 2](1.0, 2.0)
                p[0] = SIMD[f32, 2](3.0, 4.0)
                v = p[0]
                return v[1]
            """
        )
        assert mod.overwrite() == 4.0

    def test_roundtrip_all_dtypes(self):
        # one vector of each v1 dtype survives a store/load round-trip
        mod = self.compile(
            """
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
            """
        )
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
        mod = self.compile(
            """
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
            """
        )
        assert mod.entry() == 4.0  # w[2] (3.0) + first_lane(v) (1.0)

    # === elementwise arithmetic: simd.binop ===

    def test_binop_add_sub_mul_i32(self):
        mod = self.compile(
            """
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
            """
        )
        assert mod.add0(3, 4) == 7
        assert mod.sub0(10, 4) == 6
        assert mod.mul0(3, 4) == 12

    def test_binop_wraparound(self):
        # SIMD integer arithmetic follows C wraparound
        mod = self.compile(
            """
            from _simd import SIMD

            def add_u8(a: i32) -> u8:
                v = SIMD[u8, 4](u8(a))
                return (v + v)[0]

            def mul_i8(a: i32) -> i8:
                v = SIMD[i8, 4](i8(a))
                w = SIMD[i8, 4](3)
                return (v * w)[0]
            """
        )
        assert mod.add_u8(200) == 144  # 400 mod 256
        assert mod.mul_i8(100) == 44  # 300 mod 256 = 44, as signed i8

    def test_binop_add_all_dtypes(self):
        mod = self.compile(
            """
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
            """
        )
        assert mod.f_i8(5) == 10
        assert mod.f_u8(100) == 200
        assert mod.f_i32(42) == 84
        assert mod.f_u32(42) == 84
        assert mod.f_i64(42) == 84
        assert mod.f_u64(42) == 84
        assert mod.f_f32(1.5) == 3.0
        assert mod.f_f64(2.25) == 4.5

    def test_binop_float_div(self):
        mod = self.compile(
            """
            from _simd import SIMD

            def div_f32(a: f32, b: f32) -> f32:
                v = SIMD[f32, 4](a, a, a, a)
                w = SIMD[f32, 4](b, b, b, b)
                return (v / w)[0]

            def div_f64(a: f64, b: f64) -> f64:
                v = SIMD[f64, 4](a, a, a, a)
                w = SIMD[f64, 4](b, b, b, b)
                return (v / w)[0]
            """
        )
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
        mod = self.compile(
            """
            from _simd import SIMD

            def add0() -> i32:
                v = SIMD[i32, 4](1, 2, 3, 4)
                w = SIMD[i32, 4](10, 20, 30, 40)
                r = v + w
                s: i32 = 0
                for i in range(4):
                    s = s + r[i]
                return s
            """
        )
        assert mod.add0() == 110  # 11 + 22 + 33 + 44

    # === elementwise comparison: simd.cmp ===

    def test_cmp_i32(self):
        mod = self.compile(
            """
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
            """
        )
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
        mod = self.compile(
            """
            from _simd import SIMD

            def cmp_f32(a: f32, b: f32) -> i32:
                v = SIMD[f32, 4](a, a, a, a)
                w = SIMD[f32, 4](b, b, b, b)
                return (v < w)[0]

            def cmp_u8(a: i32, b: i32) -> i8:
                v = SIMD[u8, 4](u8(a))
                w = SIMD[u8, 4](u8(b))
                return (v < w)[0]
            """
        )
        assert mod.cmp_f32(1.0, 2.0) == -1
        assert mod.cmp_f32(2.0, 1.0) == 0
        assert mod.cmp_u8(1, 2) == -1
        assert mod.cmp_u8(2, 1) == 0

    def test_cmp_per_lane(self):
        mod = self.compile(
            """
            from _simd import SIMD

            def f() -> i32:
                v = SIMD[i32, 4](1, 5, 3, 7)
                w = SIMD[i32, 4](2, 4, 3, 0)
                m = v < w   # T, F, F, F
                s: i32 = 0
                for i in range(4):
                    s = s + m[i]
                return s
            """
        )
        assert mod.f() == -1  # only lane 0 is true -> one -1

    # === mask.select(a, b): simd.select ===

    def test_select_cmp_mask(self):
        mod = self.compile(
            """
            from _simd import SIMD

            def sel(a: f32, b: f32) -> f32:
                v = SIMD[f32, 4](a, a, a, a)
                w = SIMD[f32, 4](b, b, b, b)
                m = v < w
                r = m.select(v, w)
                return r[0]
            """
        )
        # a < b => mask true => select picks the first arg (v = a)
        assert mod.sel(1.0, 2.0) == 1.0
        # a > b => mask false => picks the second arg (w = b)
        assert mod.sel(3.0, 2.0) == 2.0
        # a == b => mask false => picks b
        assert mod.sel(2.0, 2.0) == 2.0

    def test_select_per_lane(self):
        mod = self.compile(
            """
            from _simd import SIMD

            def sel(idx: i32) -> f32:
                v = SIMD[f32, 4](10.0, 20.0, 30.0, 40.0)
                w = SIMD[f32, 4](1.0, 2.0, 3.0, 4.0)
                m = SIMD[i32, 4](-1, 0, -1, 0)
                r = m.select(v, w)
                return r[idx]
            """
        )
        # canonical mask lanes (-1 picks v, 0 picks w): interp == C.
        assert mod.sel(0) == 10.0
        assert mod.sel(1) == 2.0
        assert mod.sel(2) == 30.0
        assert mod.sel(3) == 4.0

    def test_select_max(self):
        # classic blend idiom: per-lane max via (a > b).select(a, b).
        mod = self.compile(
            """
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
            """
        )
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

    # === pointer load/store of whole SIMD vectors ===

    def test_ptr_load_store_roundtrip(self):
        mod = self.compile(
            """
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
            """
        )
        assert mod.roundtrip_gc(1.0, 2.0, 3.0, 4.0) == 3.0
        assert mod.roundtrip_raw(1.0, 2.0, 3.0, 4.0) == 4.0

    def test_ptr_load_store_strided_and_overwrite(self):
        mod = self.compile(
            """
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
            """
        )
        assert mod.strided() == 150  # 20 + 50 + 80
        assert mod.overwrite() == 6.0

    def test_ptr_load_store_red_index(self):
        mod = self.compile(
            """
            from unsafe import gc_alloc
            from _simd import SIMD, ptr_load_simd, ptr_store_simd

            def store_at(idx: i32) -> f32:
                p = gc_alloc[f32](8)
                ptr_store_simd(p, idx, SIMD[f32, 4](1.0, 2.0, 3.0, 4.0))
                v = ptr_load_simd[f32, 4](p, idx)
                return v[2]
            """
        )
        assert mod.store_at(0) == 3.0
        assert mod.store_at(4) == 3.0

    def test_ptr_load_store_all_dtypes(self):
        # one vector of each v1 dtype survives a load/store round-trip.
        # i64/u64 (32 B, natural align 32) exercise the unaligned lowering
        # against a normally-aligned (16 B) gc_alloc buffer.
        mod = self.compile(
            """
            from unsafe import gc_alloc
            from _simd import SIMD, ptr_load_simd, ptr_store_simd

            def rt_i8(x: i32) -> i8:
                p = gc_alloc[i8](4)
                ptr_store_simd(p, 0, SIMD[i8, 4](i8(x), i8(x), i8(x), i8(x)))
                return ptr_load_simd[i8, 4](p, 0)[0]

            def rt_u8(x: i32) -> u8:
                p = gc_alloc[u8](4)
                ptr_store_simd(p, 0, SIMD[u8, 4](u8(x), u8(x), u8(x), u8(x)))
                return ptr_load_simd[u8, 4](p, 0)[0]

            def rt_i32(x: i32) -> i32:
                p = gc_alloc[i32](4)
                ptr_store_simd(p, 0, SIMD[i32, 4](x, x, x, x))
                return ptr_load_simd[i32, 4](p, 0)[0]

            def rt_u32(x: i32) -> u32:
                p = gc_alloc[u32](4)
                ptr_store_simd(p, 0, SIMD[u32, 4](u32(x), u32(x), u32(x), u32(x)))
                return ptr_load_simd[u32, 4](p, 0)[0]

            def rt_i64(x: i32) -> i64:
                p = gc_alloc[i64](4)
                ptr_store_simd(p, 0, SIMD[i64, 4](i64(x), i64(x), i64(x), i64(x)))
                return ptr_load_simd[i64, 4](p, 0)[0]

            def rt_u64(x: i32) -> u64:
                p = gc_alloc[u64](4)
                ptr_store_simd(p, 0, SIMD[u64, 4](u64(i64(x)), u64(i64(x)), u64(i64(x)), u64(i64(x))))
                return ptr_load_simd[u64, 4](p, 0)[0]

            def rt_f32(x: f64) -> f32:
                p = gc_alloc[f32](4)
                ptr_store_simd(p, 0, SIMD[f32, 4](f32(x), f32(x), f32(x), f32(x)))
                return ptr_load_simd[f32, 4](p, 0)[0]

            def rt_f64(x: f64) -> f64:
                p = gc_alloc[f64](4)
                ptr_store_simd(p, 0, SIMD[f64, 4](x, x, x, x))
                return ptr_load_simd[f64, 4](p, 0)[0]
            """
        )
        assert mod.rt_i8(-5) == -5
        assert mod.rt_u8(200) == 200
        assert mod.rt_i32(42) == 42
        assert mod.rt_u32(42) == 42
        assert mod.rt_i64(42) == 42
        assert mod.rt_u64(42) == 42
        assert mod.rt_f32(1.5) == 1.5
        assert mod.rt_f64(2.25) == 2.25

    def test_saxpy_shape(self):
        mod = self.compile(
            """
            from unsafe import gc_alloc
            from _simd import SIMD, ptr_load_simd, ptr_store_simd

            def saxpy(a: f32, n: i32) -> f32:
                x = gc_alloc[f32](n)
                y = gc_alloc[f32](n)
                out = gc_alloc[f32](n)
                for i in range(n):
                    x[i] = 1.0
                    y[i] = 2.0
                va = SIMD[f32, 4](a)
                vx0 = ptr_load_simd[f32, 4](x, 0)
                vy0 = ptr_load_simd[f32, 4](y, 0)
                ptr_store_simd(out, 0, va * vx0 + vy0)
                vx4 = ptr_load_simd[f32, 4](x, 4)
                vy4 = ptr_load_simd[f32, 4](y, 4)
                ptr_store_simd(out, 4, va * vx4 + vy4)
                s: f32 = 0.0
                for j in range(n):
                    s = s + out[j]
                return s
            """
        )
        # out[i] = a*1 + 2 = a+2; a=3.0 -> 5.0 per element, sum = 5*n
        assert mod.saxpy(3.0, 8) == 40.0

    def test_relu_shape(self):
        # load -> compare -> select -> store.
        mod = self.compile(
            """
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
            """
        )
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
