import pytest
from spy.tests.support import CompilerTest, skip_backends, no_backend

class TestBasic(CompilerTest):

    def test_import(self, legacy):
        mod = self.compile("""
        from builtins import abs as my_abs

        def foo(x: i32) -> i32:
            return my_abs(x)
        """)
        #
        assert mod.foo(-20) == 20

    def test_import_errors(self, legacy):
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

    @skip_backends("C")
    def test_two_modules(self, legacy):
        self.write_file(
            "delta.spy",
            """
            def get_delta() -> i32:
                return 10
            """)

        self.write_file(
            "main.spy",
            """
            from delta import get_delta

            def inc(x: i32) -> i32:
                return x + get_delta()
            """)

        w_delta = self.vm.import_('delta', legacy=self._legacy)
        w_main = self.vm.import_('main', legacy=self._legacy)
        if self.backend == 'interp':
            from spy.backend.interp import InterpModuleWrapper
            delta = InterpModuleWrapper(self.vm, w_delta)
            main = InterpModuleWrapper(self.vm, w_main)
            assert delta.get_delta() == 10
            assert main.inc(4) == 14
        else:
            # we need to implement multi-module compilation to C
            assert False
