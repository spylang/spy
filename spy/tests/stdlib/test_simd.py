from spy.tests.support import CompilerTest


class TestSIMD(CompilerTest):
    def test_imports(self):
        src = """
        from simd import SIMD, simd_width_of, ptr_load_simd, ptr_store_simd
        from simd import reinterpret_as

        def width() -> i32:
            return simd_width_of[i32]

        """
        mod = self.compile(src)
        assert mod.width() == 4
