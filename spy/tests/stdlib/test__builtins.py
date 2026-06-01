from spy.tests.support import CompilerTest


class TestBuiltins(CompilerTest):
    # note: abs for i32 is already tested in test_basic.py

    def test_abs_f64(self):
        mod = self.compile(
            """
        def foo(x: f64) -> f64:
            return abs(x)
        """
        )
        assert mod.foo(10.0) == 10.0
        assert mod.foo(-20.0) == 20.0

    # note: min and max for i32 are already tested in test_basic.py

    def test_max_min_f64(self):
        mod = self.compile(
            """
        def mymax(x: f64, y: f64) -> f64: return max(x, y)
        def mymin(x: f64, y: f64) -> f64: return min(x, y)
        """
        )
        assert mod.mymax(2.0, 2.5) == 2.5
        assert mod.mymin(2.0, 2.5) == 2.0

    def test_max_min_f64_i32(self):
        mod = self.compile(
            """
        def mymax_fi(x: f64, y: i32) -> f64: return max(x, y)
        def mymin_fi(x: f64, y: i32) -> f64: return min(x, y)
        def mymax_if(x: i32, y: f64) -> f64: return max(x, y)
        def mymin_if(x: i32, y: f64) -> f64: return min(x, y)
        """
        )
        assert mod.mymax_fi(2.0, 3) == 3.0
        assert mod.mymin_fi(2.0, 3) == 2.0
        assert mod.mymax_if(2, 3.0) == 3.0
        assert mod.mymin_if(2, 3.0) == 2.0
