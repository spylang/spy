import pytest
from spy.tests.support import CompilerTest

class TestArray(CompilerTest):

    def test_array1_simple(self):
        src = """
        from array import array1

        def test() -> int:
            a = array1[int](3)
            a[0] = 1
            a[1] = 2
            a[2] = 3
            return a[0] + a[1] + a[2]
        """
        mod = self.compile(src)
        assert mod.test() == 6

    def test_len(self):
        src = """
        from array import array1

        def test() -> int:
            a = array1[int](3)
            return len(a)
        """
        mod = self.compile(src)
        assert mod.test() == 3
