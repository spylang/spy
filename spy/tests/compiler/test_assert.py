from spy.errors import SPyError
from spy.tests.support import CompilerTest, expect_errors


class TestAssert(CompilerTest):
    def test_assert_true(self):
        mod = self.compile(
            """
            def test() -> None:
                assert True
            """
        )

        mod.test()

    def test_assert_false(self):
        mod = self.compile(
            """
            def test() -> None:
                assert False
            """
        )

        with SPyError.raises("W_AssertionError"):
            mod.test()

    def test_assert_reports_original_expression(self):
        mod = self.compile(
            """
            def check_simple(actual: i32, expected: i32) -> None:
                assert actual == expected

            def check_redshifted(x: i32, expected: i32) -> None:
                assert x + 2 * 3 == expected

            def check_string(actual: str) -> None:
                assert actual == "expected"
            """
        )

        with SPyError.raises("W_AssertionError") as excinfo:
            mod.check_simple(41, 42)
        assert excinfo.value.w_exc.message == "assert actual == expected"

        with SPyError.raises("W_AssertionError") as excinfo:
            mod.check_redshifted(1, 8)
        assert excinfo.value.w_exc.message == "assert x + 2 * 3 == expected"

        with SPyError.raises("W_AssertionError") as excinfo:
            mod.check_string("actual")
        assert excinfo.value.w_exc.message == 'assert actual == "expected"'

    def test_assert_with_message(self):
        mod = self.compile(
            """
            def test() -> None:
                assert False, "custom error message"
            """
        )

        with SPyError.raises("W_AssertionError", match="custom error message"):
            mod.test()

    def test_assert_invoking_a_function(self):
        mod = self.compile(
            """
            def get_message() -> str:
                return "custom error message"

            def test() -> None:
                assert False, get_message()
            """
        )

        with SPyError.raises("W_AssertionError", match="custom error message"):
            mod.test()

    def test_assert_with_non_string_message(self):
        src = """
        def foo() -> None:
            assert False, 42
        """

        errors = expect_errors(
            "mismatched types",
            ("expected `str`, got `i32`", "42"),
        )

        self.compile_raises(src, "foo", errors)

    def test_assert_with_function_returning_non_string(self):
        src = """
        def get_error_code() -> i32:
            return 404

        def foo() -> None:
            assert False, get_error_code()
        """

        errors = expect_errors(
            "mismatched types",
            ("expected `str`, got `i32`", "get_error_code()"),
        )

        self.compile_raises(src, "foo", errors)
