from spy.tests.support import CompilerTest


class TestBuiltins(CompilerTest):
    def test_abs(self):
        src = """
        def myabs_i32(x: i32) -> i32: return abs(x)
        def myabs_f64(x: f64) -> f64: return abs(x)
        """
        mod = self.compile(src)
        assert mod.myabs_i32(10) == 10
        assert mod.myabs_i32(-20) == 20
        assert mod.myabs_f64(10.0) == 10.0
        assert mod.myabs_f64(-20.0) == 20.0

    def test_max_min(self):
        src = """
        def mymax_i32(x: i32, y: i32) -> i32: return max(x, y)
        def mymin_i32(x: i32, y: i32) -> i32: return min(x, y)

        def mymax_f64(x: f64, y: f64) -> f64: return max(x, y)
        def mymin_f64(x: f64, y: f64) -> f64: return min(x, y)
        """
        mod = self.compile(src)
        assert mod.mymax_i32(2, 3) == 3
        assert mod.mymin_i32(2, 3) == 2
        assert mod.mymax_f64(2.0, 2.5) == 2.5
        assert mod.mymin_f64(2.0, 2.5) == 2.0

    def test_max_min_f64_i32(self):
        src = """
        def mymax_fi(x: f64, y: i32) -> f64: return max(x, y)
        def mymin_fi(x: f64, y: i32) -> f64: return min(x, y)
        def mymax_if(x: i32, y: f64) -> f64: return max(x, y)
        def mymin_if(x: i32, y: f64) -> f64: return min(x, y)
        """
        mod = self.compile(src)
        assert mod.mymax_fi(2.0, 3) == 3.0
        assert mod.mymin_fi(2.0, 3) == 2.0
        assert mod.mymax_if(2, 3.0) == 3.0
        assert mod.mymin_if(2, 3.0) == 2.0
