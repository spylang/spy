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
