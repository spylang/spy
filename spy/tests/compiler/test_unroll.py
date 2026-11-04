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

    def test_target_is_blue(self):
        src = """
        from __spy__ import COLOR, interp_tuple

        TUP = interp_tuple(1, 2, 3)

        def foo() -> i32:
            n = 0
            for i in unroll(TUP):
                if COLOR(i) == "blue":
                    n = n + 1
            return n
        """
        mod = self.compile(src)
        assert mod.foo() == 3

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

    def test_unroll_inner_loop(self):
        src = """
        from __spy__ import interp_tuple

        TUP = interp_tuple(1, 2)

        def foo() -> i32:
            total = 0
            for x in range(3):
                for i in unroll(TUP):
                    y = x + i
                    total = total + y
            return total
        """
        mod = self.compile(src)
        assert mod.foo() == 15

    def test_nested_unroll(self):
        src = """
        from __spy__ import interp_tuple

        A = interp_tuple(1, 2)
        B = interp_tuple(10, 20)

        def foo() -> i32:
            total = 0
            for i in unroll(A):
                x = i * 100
                for j in unroll(B):
                    y = x + j
                    total = total + y
            return total
        """
        mod = self.compile(src)
        assert mod.foo() == 660

    def test_two_unrolls_same_target_name(self):
        src = """
        from __spy__ import interp_tuple

        A = interp_tuple(1, 2)
        B = interp_tuple(10, 20)

        def foo() -> i32:
            total = 0
            for i in unroll(A):
                x = i
                total = total + x
            for i in unroll(B):
                x = i
                total = total + x
            return total
        """
        mod = self.compile(src)
        assert mod.foo() == 33

    def test_break_continue_in_inner_loop(self):
        src = """
        from __spy__ import interp_tuple

        TUP = interp_tuple(1, 2)

        def foo() -> i32:
            total = 0
            for i in unroll(TUP):
                n = 0
                while True:
                    n = n + 1
                    if n == 3:
                        break
                    continue
                total = total + i * 100 + n
            return total
        """
        mod = self.compile(src)
        assert mod.foo() == 306

    def test_unroll_must_be_the_builtin(self):
        src = """
        from __spy__ import interp_tuple

        def unroll(x: dynamic) -> dynamic:
            return x

        TUP = interp_tuple(1, 2)

        def foo() -> None:
            for i in unroll(TUP):
                pass
        """
        errors = expect_errors(
            "invalid `unroll` function",
            ("this is not `builtins::unroll`", "unroll"),
            ("`unroll` defined here", "def unroll(x: dynamic) -> dynamic"),
        )
        self.compile_raises(src, "foo", errors)
