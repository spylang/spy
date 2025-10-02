import pytest
from spy.errors import SPyError
from spy.tests.support import CompilerTest


class TestAssert(CompilerTest):
    def test_assert_true(self):
        """Test that assert True passes without error"""
        mod = self.compile(
            """
            def test() -> None:
                assert True
            """
        )

        mod.test()

    def test_assert_false(self):
        """Test that assert False raises AssertionError"""
        mod = self.compile(
            """
            def test() -> None:
                assert False
            """
        )

        with pytest.raises(SPyError) as exc_info:
            mod.test()

        assert exc_info.value.etype == "W_AssertionError"

    def test_assert_with_message(self):
        """Test assert with custom message"""
        mod = self.compile(
            """
            def test() -> None:
                assert False, "custom error message"
            """
        )

        with pytest.raises(SPyError) as exc_info:
            mod.test()

        assert exc_info.value.etype == "W_AssertionError"
        assert "custom error message" in str(exc_info.value.w_exc.message)

    def test_assert_invoking_a_function(self):
        """Test assert with a message retrieved by a function call"""
        mod = self.compile(
            """
            def get_message() -> str:
                return "custom error message"

            def test() -> None:
                assert False, get_message()
            """
        )

        with pytest.raises(SPyError) as exc_info:
            mod.test()

        assert exc_info.value.etype == "W_AssertionError"
        assert "custom error message" in str(exc_info.value.w_exc.message)

    def test_assert_with_non_string_message(self):
        """Test assert with non-string message raises TypeError"""
        with pytest.raises(SPyError) as exc_info:
            self.compile(
                """
                def test() -> None:
                    assert False, 42
                """
            ).test()

        assert exc_info.value.etype == "W_TypeError"
        assert "expected `str`, got `i32`" in str(exc_info.value)

    def test_assert_with_function_returning_non_string(self):
        """Test assert with function call returning non-string raises TypeError"""
        with pytest.raises(SPyError) as exc_info:
            self.compile(
                """
                def get_error_code() -> i32:
                    return 404
                    
                def test() -> None:
                    assert False, get_error_code()
                """
            ).test()

        assert exc_info.value.etype == "W_TypeError"
        assert "expected `str`, got `i32`" in str(exc_info.value)
