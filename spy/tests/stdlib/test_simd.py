from spy.tests.support import CompilerTest
from spy.vm.struct import UnwrappedStruct


def _as_tuple(unwrapped_tuple: UnwrappedStruct) -> tuple:
    return tuple(unwrapped_tuple._content.values())


class TestSIMD(CompilerTest):
    def test_imports(self):
        src = """
        from simd import SIMD, simd_width_of, ptr_load_simd, ptr_store_simd
        from simd import reinterpret_as, min, max, abs, clamp

        def width() -> i32:
            return simd_width_of[i32]

        """
        mod = self.compile(src)
        assert mod.width() == 4

    def test_min_max(self):
        mod = self.compile("""
            from simd import SIMD, min, max

            def min_max[T](a: T, b: T) -> tuple[T, T]:
                va = SIMD[T, 4](a, a, a, a)
                vb = SIMD[T, 4](b, b, b, b)
                return min(va, vb)[0], max(va, vb)[0]

            mm_i32 = min_max[i32]
            mm_f32 = min_max[f32]
            """)
        assert _as_tuple(mod.mm_f32(1.0, 2.0)) == (1.0, 2.0)
        assert _as_tuple(mod.mm_f32(3.0, 2.0)) == (2.0, 3.0)
        assert _as_tuple(mod.mm_i32(5, 3)) == (3, 5)
        assert _as_tuple(mod.mm_i32(-1, -5)) == (-5, -1)

    def test_abs_clamp(self):
        mod = self.compile("""
            from simd import SIMD, abs, clamp

            def t_abs() -> tuple[f32, f32, f32, f32]:
                v = SIMD[f32, 4](-1.0, 2.0, -3.0, 4.0)
                w = abs(v)
                return (w[0], w[1], w[2], w[3])

            def t_clamp() -> tuple[f32, f32, f32, f32]:
                vx = SIMD[f32, 4](-5.0, 5.0, 15.0, 25.0)
                vl = SIMD[f32, 4](0.0, 0.0, 10.0, 20.0)
                vh = SIMD[f32, 4](10.0, 10.0, 20.0, 30.0)
                wc = clamp(vx, vl, vh)
                return (wc[0], wc[1], wc[2], wc[3])
                """)
        assert _as_tuple(mod.t_abs()) == (1.0, 2.0, 3.0, 4.0)
        assert _as_tuple(mod.t_clamp()) == (0.0, 5.0, 15.0, 25.0)
