from spy.tests.support import CompilerTest


class TestXXDemo(CompilerTest):

    def test_double(self):
        src = """
        from xxdemo import double

        def test() -> int:
            return double(5)
        """
        mod = self.compile(src)
        assert mod.test() == 10
