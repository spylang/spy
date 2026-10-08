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

    def test_all_dtypes(self):
        src = """
        from _simd import SIMD

        def func[T](x: T) -> T:
            v = SIMD[T, 4].splat(x)
            return v[0]

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
        assert mod.f_i8(-5) == -5
        assert mod.f_u8(200) == 200
        assert mod.f_i32(42) == 42
        assert mod.f_u32(42) == 42
        assert mod.f_i64(42) == 42
        assert mod.f_u64(42) == 42
        assert mod.f_f32(1.5) == 1.5
        assert mod.f_f64(2.25) == 2.25

    def _check_invalid(self, params: str, msg: str, extra: str = "") -> None:
        src = f"""
        from _simd import SIMD
        {extra}
        def bad() -> None:
            v = SIMD[{params}]
        """
        self.compile_raises(src, "bad", expect_errors(msg))

    def test_invalid_size_not_power_of_two(self):
        self._check_invalid("f32, 3", "SIMD size must be a power of two, got 3")

    def test_invalid_size_zero(self):
        self._check_invalid(
            "f32, 0", "SIMD size must be a positive power of two, got 0"
        )

    def test_invalid_size_negative(self):
        self._check_invalid(
            "f32, -2", "SIMD size must be a positive power of two, got -2"
        )

    def test_invalid_dtype_bool(self):
        self._check_invalid(
            "bool, 4", "SIMD element type must be a numeric primitive, got `bool`"
        )

    def test_invalid_dtype_str(self):
        self._check_invalid(
            "str, 4", "SIMD element type must be a numeric primitive, got `str`"
        )

    def test_invalid_dtype_struct(self):
        extra = """
        @struct
        class Point:
            x: i32
            y: i32
        """
        self._check_invalid(
            "Point, 4",
            "SIMD element type must be a numeric primitive, got `test::Point`",
            extra,
        )

    def test_constructors(self):
        src = """
        from _simd import SIMD

        VEC = SIMD[i32, 4]

        def lanes(v: VEC) -> tuple[i32, i32, i32, i32]:
            return v[0], v[1], v[2], v[3]

        def zeros() -> tuple[i32, i32, i32, i32]:
            return lanes(VEC.zeros())

        def splat(x: i32) -> tuple[i32, i32, i32, i32]:
            return lanes(VEC.splat(x))

        def explicit(a: i32, b: i32, c: i32, d: i32) -> tuple[i32, i32, i32, i32]:
            return lanes(VEC(a, b, c, d))

        def convert(a: i32, b: i32, c: i32, d: i32) -> tuple[i32, i32, i32, i32]:
            v: VEC = [a, b, c, d]
            return lanes(v)

        def splat_is_explicit(x: i32) -> bool:
            v = VEC.splat(x)
            w = VEC(x, x, x, x)
            return lanes(v) == lanes(w)
        """
        mod = self.compile(src)
        assert mod.zeros() == (0, 0, 0, 0)
        assert mod.splat(42) == (42, 42, 42, 42)
        assert mod.explicit(1, 2, 3, 4) == (1, 2, 3, 4)
        assert mod.convert(5, 6, 7, 8) == (5, 6, 7, 8)
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

    def test_immutable(self):
        src = """
        from _simd import SIMD

        def bad() -> None:
            v = SIMD[i32, 4].zeros()
            v[0] = 99
        """
        errors = expect_errors(
            "type `SIMD[i32, 4]` does not support item assignment",
            ("this is `SIMD[i32, 4]`", "v"),
        )
        self.compile_raises(src, "bad", errors)

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
