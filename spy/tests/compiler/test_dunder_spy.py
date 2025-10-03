from spy.tests.support import CompilerTest

class TestDunderSpy(CompilerTest):

    def test_is_compiled(self):
        mod = self.compile(
        """
        from __spy__ import is_compiled

        def foo() -> bool:
            return is_compiled()
        """)
        if self.backend in ('interp', 'doppler'):
            assert mod.foo() == False
        else:
            assert mod.foo() == True
