from spy.errors import SPyError
from spy.tests.support import CompilerTest, expect_errors


class TestBlueFrame(CompilerTest):
    def test_simple(self):
        src = """
        from __spy__ import force_blue

        @blue
        def inc(x):
            return x + 1

        @blue
        def foo():
            var x = 1
            return inc(force_blue(x))

        def bar() -> i32:
            return foo()
        """
        mod = self.compile(src)
        assert mod.bar() == 2

    def test_force_blue_in_red_frame(self):
        src = """
        from __spy__ import force_blue

        def foo() -> i32:
            return force_blue(1)
        """
        errors = expect_errors(
            "force_blue can be used only in a blue frame",
            ("this frame is red", "force_blue(1)"),
        )
        self.compile_raises(src, "foo", errors)
