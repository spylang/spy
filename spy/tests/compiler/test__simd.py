from spy.errors import SPyError
from spy.tests.support import CompilerTest, expect_errors, only_interp


class TestSIMD(CompilerTest):
    def test_sizes(self):
        src = """
        from _simd import SIMD

        def get_last[N](x: i32) -> i32:
            v = SIMD[i32, N].splat(x)
            return v[N - 1]

        s1 = get_last[1]
        s2 = get_last[2]
        s4 = get_last[4]
        s8 = get_last[8]
        """
        mod = self.compile(src)
        assert mod.s1(1) == 1
        assert mod.s2(2) == 2
        assert mod.s4(3) == 3
        assert mod.s8(7) == 7

    @only_interp
    def test_invalid_params(self):
        src = """
        from _simd import SIMD

        @struct
        class Point:
            x: i32
            y: i32

        def length_not_power_of_two() -> None:
            v = SIMD[f32, 3]

        def length_zero() -> None:
            v = SIMD[f32, 0]

        def length_negative() -> None:
            v = SIMD[f32, -2]

        def dtype_bool() -> None:
            v = SIMD[bool, 4]

        def dtype_str() -> None:
            v = SIMD[str, 4]

        def dtype_struct() -> None:
            v = SIMD[Point, 4]
        """

        def check_error(funcname: str, msg: str) -> None:
            self.compile_raises(src, funcname, expect_errors(msg))

        check_error(
            "length_not_power_of_two", "SIMD length must be a power of two, got 3"
        )
        check_error("length_zero", "SIMD length must be a positive power of two, got 0")
        check_error(
            "length_negative", "SIMD length must be a positive power of two, got -2"
        )
        check_error(
            "dtype_bool", "SIMD element type must be a numeric primitive, got `bool`"
        )
        check_error(
            "dtype_str", "SIMD element type must be a numeric primitive, got `str`"
        )
        check_error(
            "dtype_struct",
            "SIMD element type must be a numeric primitive, got `test::Point`",
        )

    def test_constructors(self):
        src = """
        from __spy__ import COLOR
        from _simd import SIMD

        VEC = SIMD[i32, 4]

        def lanes(v: VEC) -> tuple[i32, i32, i32, i32]:
            return v[0], v[1], v[2], v[3]

        def zeros() -> tuple[i32, i32, i32, i32]:
            v = VEC.zeros()
            assert COLOR(v) == "blue"
            return lanes(v)

        def splat(x: i32) -> tuple[i32, i32, i32, i32]:
            return lanes(VEC.splat(x))

        def splat_literal() -> tuple[i32, i32, i32, i32]:
            v = VEC.splat(42)
            assert COLOR(v) == "blue"
            return lanes(v)

        def explicit(a: i32, b: i32, c: i32, d: i32) -> tuple[i32, i32, i32, i32]:
            return lanes(VEC(a, b, c, d))

        def convert(a: i32, b: i32, c: i32, d: i32) -> tuple[i32, i32, i32, i32]:
            v: VEC = [a, b, c, d]
            return lanes(v)

        def convert_blue_tuple() -> tuple[i32, i32, i32, i32]:
            tup = (1, 2, 3, 4)
            assert COLOR(tup) == "blue"
            v: VEC = tup
            assert COLOR(v) == "blue"
            return lanes(v)

        def splat_is_explicit(x: i32) -> bool:
            v = VEC.splat(x)
            w = VEC(x, x, x, x)
            return lanes(v) == lanes(w)
        """
        mod = self.compile(src)
        assert mod.zeros() == (0, 0, 0, 0)
        assert mod.splat(42) == (42, 42, 42, 42)
        assert mod.splat_literal() == (42, 42, 42, 42)
        assert mod.explicit(1, 2, 3, 4) == (1, 2, 3, 4)
        assert mod.convert(5, 6, 7, 8) == (5, 6, 7, 8)
        assert mod.convert_blue_tuple() == (1, 2, 3, 4)
        assert mod.splat_is_explicit(9)

    def test_constructors_all_dtypes(self):
        src = """
        from _simd import SIMD

        def func[T](x: T) -> tuple[T, T, T, T]:
            z = SIMD[T, 4].zeros()
            s = SIMD[T, 4].splat(x)
            v = SIMD[T, 4](z[0], s[1], x, z[3])
            return v[0], v[1], v[2], v[3]

        f_i8 = func[i8]
        f_u8 = func[u8]
        f_i32 = func[i32]
        f_u32 = func[u32]
        f_i64 = func[i64]
        f_u64 = func[u64]
        f_f32 = func[f32]
        f_f64 = func[f64]
        """
        mod = self.compile(src)
        assert mod.f_i8(-5) == (0, -5, -5, 0)
        assert mod.f_u8(200) == (0, 200, 200, 0)
        assert mod.f_i32(-42) == (0, -42, -42, 0)
        assert mod.f_u32(42) == (0, 42, 42, 0)
        assert mod.f_i64(-42) == (0, -42, -42, 0)
        assert mod.f_u64(42) == (0, 42, 42, 0)
        assert mod.f_f32(1.5) == (0.0, 1.5, 1.5, 0.0)
        assert mod.f_f64(2.25) == (0.0, 2.25, 2.25, 0.0)

    def test_no_default_constructor(self):
        src = """
        from _simd import SIMD

        VEC = SIMD[i32, 4]

        def bad() -> None:
            v = VEC()
        """
        errors = expect_errors(
            "SIMD requires explicit initialization",
            (
                "use `SIMD[i32, 4].zeros()`, `SIMD[i32, 4].splat(x)` or pass 4 values",
                "VEC",
            ),
        )
        self.compile_raises(src, "bad", errors)

    def test_wrong_number_of_args(self):
        src = """
        from _simd import SIMD

        def bad() -> None:
            v = SIMD[i32, 4](1, 2)
        """
        errors = expect_errors(
            "`SIMD[i32, 4]` expects 4 values, got 2",
            ("this is `SIMD[i32, 4]`", "SIMD[i32, 4]"),
        )
        self.compile_raises(src, "bad", errors)

    def test_convert_from_list_and_tuple(self):
        # items are implicitly converted to the dtype: here i32 -> f64
        src = """
        from _simd import SIMD

        VEC = SIMD[f64, 2]

        def list_literal() -> tuple[f64, f64]:
            v: VEC = [1, 2]
            return v[0], v[1]

        def tuple_literal() -> tuple[f64, f64]:
            v: VEC = (1, 2)
            return v[0], v[1]

        def list_runtime(a: i32, b: i32) -> tuple[f64, f64]:
            v: VEC = [a, b]
            return v[0], v[1]

        def tuple_runtime(a: i32, b: f64) -> tuple[f64, f64]:
            v: VEC = (a, b)
            return v[0], v[1]
        """
        mod = self.compile(src)
        assert mod.list_literal() == (1.0, 2.0)
        assert mod.tuple_literal() == (1.0, 2.0)
        assert mod.list_runtime(1, 2) == (1.0, 2.0)
        assert mod.tuple_runtime(1, 2.5) == (1.0, 2.5)

    def test_convert_from_tuple_wrong_length(self):
        # the length of a tuple is part of its type: this is a compile-time error
        src = """
        from _simd import SIMD

        def bad() -> None:
            v: SIMD[f64, 2] = (1, 2, 3)
        """
        errors = expect_errors(
            "`SIMD[f64, 2]` expects 2 values, got 3",
            ("this is `tuple[i32, i32, i32]`", "(1, 2, 3)"),
        )
        self.compile_raises(src, "bad", errors)

    def test_convert_from_wrong_length(self):
        # the length of a list is known only at runtime
        src = """
        from _simd import SIMD

        def bad(n: i32) -> i32:
            lst = [1, 2, 3]
            v: SIMD[i32, 4] = lst
            return v[0]
        """
        mod = self.compile(src)
        with SPyError.raises("W_ValueError", match="expected 4 elements"):
            mod.bad(0)

    def test_runtime_index(self):
        src = """
        from _simd import SIMD

        def get_lane(idx: i32) -> f64:
            v = SIMD[f64, 4](10.0, 20.0, 30.0, 40.0)
            return v[idx]

        def sum_lanes(a: i32, b: i32, c: i32, d: i32) -> i32:
            v = SIMD[i32, 4](a, b, c, d)
            s: i32 = 0
            for i in range(4):
                s = s + v[i]
            return s
        """
        mod = self.compile(src)
        assert [mod.get_lane(i) for i in range(4)] == [10.0, 20.0, 30.0, 40.0]
        assert mod.sum_lanes(1, 2, 3, 4) == 10
        assert mod.sum_lanes(10, 20, 30, 40) == 100

    @only_interp
    def test_index_out_of_bounds(self):
        src = """
        from _simd import SIMD

        def bad(i: i32) -> f32:
            v = SIMD[f32, 4].splat(1.0)
            return v[i]
        """
        mod = self.compile(src)
        with SPyError.raises("W_PanicError", match="SIMD index out of bounds"):
            mod.bad(4)
        with SPyError.raises("W_PanicError", match="SIMD index out of bounds"):
            mod.bad(-1)

    def test_store_load(self):
        src = """
        from unsafe import gc_alloc, gc_ptr
        from _simd import SIMD

        VEC = SIMD[i32, 2]

        def roundtrip(a: i32, b: i32) -> tuple[i32, i32]:
            p: gc_ptr[VEC] = gc_alloc[VEC](1)
            p[0] = VEC(a, b)
            v = p[0]
            return v[0], v[1]

        def overwrite() -> tuple[i32, i32]:
            p: gc_ptr[VEC] = gc_alloc[VEC](1)
            p[0] = VEC(1, 2)
            p[0] = VEC(3, 4)
            v = p[0]
            return v[0], v[1]

        def multiple() -> i32:
            p: gc_ptr[VEC] = gc_alloc[VEC](3)
            p[0] = VEC(1, 2)
            p[1] = VEC(3, 4)
            p[2] = VEC(5, 6)
            s: i32 = 0
            for i in range(3):
                v = p[i]
                s = s + v[0] + v[1]
            return s
        """
        mod = self.compile(src)
        assert mod.roundtrip(7, 8) == (7, 8)
        assert mod.overwrite() == (3, 4)
        assert mod.multiple() == 21

    def test_store_load_all_dtypes(self):
        src = """
        from unsafe import gc_alloc, gc_ptr
        from _simd import SIMD

        def func[T](x: T) -> tuple[T, T]:
            p: gc_ptr[SIMD[T, 2]] = gc_alloc[SIMD[T, 2]](1)
            p[0] = SIMD[T, 2].splat(x)
            v = p[0]
            return v[0], v[1]

        rt_i8 = func[i8]
        rt_u8 = func[u8]
        rt_i32 = func[i32]
        rt_u32 = func[u32]
        rt_i64 = func[i64]
        rt_u64 = func[u64]
        rt_f32 = func[f32]
        rt_f64 = func[f64]
        """
        mod = self.compile(src)
        assert mod.rt_i8(-5) == (-5, -5)
        assert mod.rt_u8(200) == (200, 200)
        assert mod.rt_i32(-42) == (-42, -42)
        assert mod.rt_u32(42) == (42, 42)
        assert mod.rt_i64(-42) == (-42, -42)
        assert mod.rt_u64(42) == (42, 42)
        assert mod.rt_f32(1.5) == (1.5, 1.5)
        assert mod.rt_f64(2.25) == (2.25, 2.25)

    def test_pass_and_return_by_value(self):
        src = """
        from _simd import SIMD

        VEC = SIMD[f32, 4]

        def identity(v: VEC) -> VEC:
            return v

        def entry() -> tuple[f32, f32, f32, f32]:
            v = VEC(1.0, 2.0, 3.0, 4.0)
            w = identity(v)
            return w[0], w[1], w[2], w[3]
        """
        mod = self.compile(src)
        assert mod.entry() == (1.0, 2.0, 3.0, 4.0)

    def test_iota(self):
        src = """
        from __spy__ import COLOR
        from _simd import SIMD

        def lanes[T](v: SIMD[T, 4]) -> tuple[T, T, T, T]:
            return v[0], v[1], v[2], v[3]

        def default[T]() -> tuple[T, T, T, T]:
            v = SIMD[T, 4].iota()
            assert COLOR(v) == "blue"
            return lanes[T](v)

        def start[T](start: T) -> tuple[T, T, T, T]:
            return lanes[T](SIMD[T, 4].iota(start))

        def start_step[T](start: T, step: T) -> tuple[T, T, T, T]:
            return lanes[T](SIMD[T, 4].iota(start, step))

        def blue_literals() -> tuple[i32, i32, i32, i32]:
            v = SIMD[i32, 4].iota(10, 2)
            assert COLOR(v) == "blue"
            return lanes[i32](v)

        def last[T, N]() -> T:
            return SIMD[T, N].iota()[N - 1]

        def last_start_step[T, N](start: T, step: T) -> T:
            return SIMD[T, N].iota(start, step)[N - 1]

        default_i32 = default[i32]
        default_u32 = default[u32]
        default_f64 = default[f64]

        start_i32 = start[i32]
        start_u32 = start[u32]
        start_f64 = start[f64]

        start_step_i32 = start_step[i32]
        start_step_u32 = start_step[u32]
        start_step_f64 = start_step[f64]

        last_1 = last[i32, 1]
        last_2 = last[i32, 2]
        last_8 = last[i32, 8]
        last_16 = last[i32, 16]
        last_ss_1 = last_start_step[i32, 1]
        last_ss_8 = last_start_step[i32, 8]
        """
        mod = self.compile(src)

        assert mod.default_i32() == (0, 1, 2, 3)
        assert mod.default_u32() == (0, 1, 2, 3)
        assert mod.default_f64() == (0.0, 1.0, 2.0, 3.0)

        assert mod.start_i32(10) == (10, 11, 12, 13)
        assert mod.start_i32(-2) == (-2, -1, 0, 1)
        assert mod.start_u32(10) == (10, 11, 12, 13)
        assert mod.start_f64(0.5) == (0.5, 1.5, 2.5, 3.5)

        assert mod.start_step_i32(10, 2) == (10, 12, 14, 16)
        assert mod.start_step_i32(0, -1) == (0, -1, -2, -3)
        assert mod.start_step_i32(5, 0) == (5, 5, 5, 5)
        assert mod.start_step_u32(10, 3) == (10, 13, 16, 19)
        assert mod.start_step_f64(0.5, -0.25) == (0.5, 0.25, 0.0, -0.25)

        assert mod.blue_literals() == (10, 12, 14, 16)

        assert mod.last_1() == 0
        assert mod.last_2() == 1
        assert mod.last_8() == 7
        assert mod.last_16() == 15
        assert mod.last_ss_1(100, 3) == 100
        assert mod.last_ss_8(100, 3) == 121

        i32_min, i32_max = -(2**31), 2**31 - 1
        u32_max = 2**32 - 1
        # only the lanes have to fit in the dtype, not `step * i`
        assert mod.start_step_i32(i32_min, 2**30) == tuple(
            i32_min + i * 2**30 for i in range(4)
        )
        assert mod.last_ss_1(7, i32_max) == 7
        assert mod.start_step_i32(i32_min, 1) == tuple(i32_min + i for i in range(4))
        assert mod.start_step_i32(i32_max - 3, 1) == tuple(
            i32_max - 3 + i for i in range(4)
        )
        assert mod.start_step_u32(u32_max - 3, 1) == tuple(
            u32_max - 3 + i for i in range(4)
        )

        # red arguments: overflow raises at runtime instead of wrapping
        with SPyError.raises("W_PanicError", match="overflows `i32`"):
            mod.start_step_i32(i32_max - 1, 1)
        with SPyError.raises("W_PanicError", match="overflows `i32`"):
            mod.start_step_i32(i32_min, -1)
        with SPyError.raises("W_PanicError", match="overflows `u32`"):
            mod.start_step_u32(u32_max - 2, 1)

    @only_interp
    def test_iota_overflow(self):
        # when start and step are blue, we know all the lanes at compile time
        src = """
        from _simd import SIMD

        def default_u8() -> None:
            v = SIMD[u8, 1024].iota()

        def default_i8() -> None:
            v = SIMD[i8, 256].iota()

        def start_u8() -> None:
            v = SIMD[u8, 4].iota(254)

        def start_i8() -> None:
            v = SIMD[i8, 256].iota(-129)

        def negative_step_u8() -> None:
            v = SIMD[u8, 4].iota(2, -1)

        def big_step_i32() -> None:
            v = SIMD[i32, 4].iota(0, 1_000_000_000)
        """

        def check_error(funcname: str, msg: str, t: str) -> None:
            errors = expect_errors(msg, (f"this is `{t}`", t))
            self.compile_raises(src, funcname, errors)

        check_error(
            "default_u8",
            "`SIMD[u8, 1024].iota` overflows `u8`: lane 256 would be 256",
            "SIMD[u8, 1024]",
        )
        check_error(
            "default_i8",
            "`SIMD[i8, 256].iota` overflows `i8`: lane 128 would be 128",
            "SIMD[i8, 256]",
        )
        check_error(
            "start_u8",
            "`SIMD[u8, 4].iota` overflows `u8`: lane 2 would be 256",
            "SIMD[u8, 4]",
        )
        check_error(
            "start_i8",
            "`SIMD[i8, 256].iota` overflows `i8`: lane 0 would be -129",
            "SIMD[i8, 256]",
        )
        check_error(
            "negative_step_u8",
            "`SIMD[u8, 4].iota` overflows `u8`: lane 3 would be -1",
            "SIMD[u8, 4]",
        )
        check_error(
            "big_step_i32",
            "`SIMD[i32, 4].iota` overflows `i32`: lane 3 would be 3000000000",
            "SIMD[i32, 4]",
        )
