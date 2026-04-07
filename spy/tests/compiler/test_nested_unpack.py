from spy.tests.support import CompilerTest

class TestNestedUnpack(CompilerTest):

    def test_nested_unpack_basic(self):
        mod = self.compile("""
        def main() -> i32:
            tup = (1, (2, 3))
            a, (b, c) = tup
            return a + b + c
        """)
        assert mod.main() == 6

    def test_nested_unpack_deep(self):
        mod = self.compile("""
        def main() -> i32:
            tup = (1, (2, (3, 4)))
            a, (b, (c, d)) = tup
            return a + b + c + d
        """)
        assert mod.main() == 10

    def test_nested_unpack_multiple(self):
        mod = self.compile("""
        def main() -> i32:
            tup = ((1, 2), (3, 4))
            (a, b), (c, d) = tup
            return a + b + c + d
        """)
        assert mod.main() == 10
