import pytest
from spy.tests.support import CompilerTest, no_C, expect_errors

class TestImporting(CompilerTest):

    def test_import(self):
        mod = self.compile("""
        from builtins import abs as my_abs

        def foo(x: i32) -> i32:
            return my_abs(x)
        """)
        #
        assert mod.foo(-20) == 20

    def test_import_errors_1(self):
        ctx = expect_errors(
            'cannot import `builtins.aaa`',
            ('attribute `aaa` does not exist in module `builtins`', 'aaa')
        )
        with ctx:
            self.compile("""
            from builtins import aaa
            """)

    def test_import_errors_2(self):
        ctx = expect_errors(
            'cannot import `xxx.aaa`',
            ('module `xxx` does not exist', 'from xxx import aaa'),
        )
        with ctx:
            self.compile("""
            from xxx import aaa
            """)

    # we need to implement multi-module compilation to C
    @no_C
    def test_two_modules(self):
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

        w_delta = self.vm.import_('delta')
        w_main = self.vm.import_('main')
        if self.backend == 'interp':
            from spy.backend.interp import InterpModuleWrapper
            delta = InterpModuleWrapper(self.vm, w_delta)
            main = InterpModuleWrapper(self.vm, w_main)
            assert delta.get_delta() == 10
            assert main.inc(4) == 14
