import pytest

from spy.tests.support import CompilerTest, only_interp


@pytest.fixture(params=["i32", "i8", "u8"])
def int_type(request):
    return request.param


class TestUnsafeInt(CompilerTest):
    def test_unchecked_div(self, int_type):
        mod = self.compile(f"""
        from unsafe import unchecked_div
        T = {int_type}
        def div(x: T, y: T) -> f64: return unchecked_div(x, y)
        """)
        assert mod.div(7, 2) == 3.5
        assert mod.div(120, 16) == 7.5
        assert mod.div(45, 60) == 0.75

    def test_unchecked_floordiv(self, int_type):
        mod = self.compile(f"""
        from unsafe import unchecked_floordiv
        T = {int_type}
        def floordiv(x: T, y: T) -> T: return unchecked_floordiv(x, y)
        """)
        assert mod.floordiv(7, 2) == 3
        assert mod.floordiv(120, 16) == 7
        assert mod.floordiv(45, 60) == 0

    def test_unchecked_mod(self, int_type):
        mod = self.compile(f"""
        from unsafe import unchecked_mod
        T = {int_type}
        def mod(x: T, y: T) -> T: return unchecked_mod(x, y)
        """)
        assert mod.mod(10, 3) == 1
        assert mod.mod(122, 2) == 0
        assert mod.mod(116, 5) == 1

    def test_floordiv_mod_mixed_signs(self, int_type):
        if int_type == "u8":
            pytest.skip("Skipping for negative operands in floordiv test")

        mod = self.compile(f"""
        from unsafe import unchecked_floordiv, unchecked_mod
        T = {int_type}
        def floordiv(x: T, y: T) -> T: return unchecked_floordiv(x, y)
        def mod(x: T, y: T) -> T: return unchecked_mod(x, y)
        """)
        assert mod.floordiv(7, 3) == 2
        assert mod.floordiv(-7, 3) == -3
        assert mod.floordiv(7, -3) == -3
        assert mod.floordiv(-7, -3) == 2
        assert mod.mod(7, 3) == 1
        assert mod.mod(-7, 3) == 2
        assert mod.mod(7, -3) == -2
        assert mod.mod(-7, -3) == -1

    @only_interp
    def test_spy_zero_division_unchecked(self, int_type):
        mod = self.compile(f"""
        from unsafe import unchecked_div, unchecked_floordiv, unchecked_mod
        T = {int_type}
        def div(x: T, y: T) -> T: return unchecked_div(x, y)
        def floordiv(x: T, y: T) -> T: return unchecked_floordiv(x, y)
        def mod(x: T, y: T) -> T: return unchecked_mod(x, y)
        """)
        try:
            mod.div(11, 0)
        except ZeroDivisionError:
            pass

        try:
            mod.floordiv(11, 0)
        except ZeroDivisionError:
            pass

        try:
            mod.mod(10, 0)
        except ZeroDivisionError:
            pass
