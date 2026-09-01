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
