from spy.tests.support import CompilerTest, only_py_cffi


@only_py_cffi
class TestPyCFFI(CompilerTest):
    def test_simple(self):
        mod = self.compile("""
        def add(x: i32, y: i32) -> i32:
            return x + y
        """)
        assert mod.__name__ == "test"  # this is 'pyfile'
        assert hasattr(mod._test, "ffi")  # this is the cffi ext mode
        assert mod.add is mod._test.lib.spy_test_add
        assert mod.add(4, 5) == 9
