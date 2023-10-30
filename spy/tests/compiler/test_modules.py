import pytest
from spy.tests.support import CompilerTest, skip_backends, no_backend

class TestBasic(CompilerTest):

    def test_import(self):
        mod = self.compile("""
        from builtins import abs as my_abs

        def foo(x: i32) -> i32:
            return my_abs(x)
        """)
        #
        assert mod.foo(-20) == 20

    def test_import_errors(self):
        self.expect_errors(
            """
            from builtins import aaa
            """,
            errors = [
                'cannot import `builtins.aaa`',
                'attribute `aaa` does not exist in module `builtins`'
            ]
        )
        self.expect_errors(
            """
            from xxx import aaa
            """,
            errors = [
                'cannot import `xxx.aaa`',
                'module `xxx` does not exist'
            ]
        )
