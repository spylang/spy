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
