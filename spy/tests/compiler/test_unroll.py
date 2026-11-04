from spy.tests.support import CompilerTest, expect_errors


class TestUnroll(CompilerTest):
    def test_for_unroll(self):
        src = """
        from __spy__ import interp_tuple

        TUP = interp_tuple(1, 2, 3)

        def foo() -> i32:
            total = 0
            for i in unroll(TUP):
                y = i * 2
                total = total + y
            return total
        """
        mod = self.compile(src)
        assert mod.foo() == 12

    def test_for_unroll_red_iterable(self):
        src = """
        def foo() -> i32:
            return bar(10)

        def bar(n: i32) -> i32:
            total = 0
            for i in unroll(range(n)):
                total = total + i
            return total
        """
        errors = expect_errors(
            "unroll() requires a blue iterable",
            ("this is red", "range(n)"),
        )
        self.compile_raises(src, "foo", errors)
