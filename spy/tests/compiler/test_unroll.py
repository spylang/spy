from spy.tests.support import CompilerTest, expect_errors


class TestUnroll(CompilerTest):
    def test_simple(self):
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

    def test_must_have_blue_iterable(self):
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

    def test_body_locals_change_type(self):
        src = """
        from __spy__ import interp_tuple

        TUP = interp_tuple(1, 2.5, "hello")

        def foo() -> i32:
            n = 0
            for i in unroll(TUP):
                item = i
                n = n + 1
            return n
        """
        mod = self.compile(src)
        assert mod.foo() == 3
