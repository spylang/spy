import pytest
from spy.tests.support import CompilerTest

class TestArray(CompilerTest):

    def test_array1_simple(self):
        src = """
        from array import array

        def test() -> int:
            a = array[int, 1](3)
            a[0] = 1
            a[1] = 2
            a[2] = 3
            return a[0] + a[1] + a[2]
        """
        mod = self.compile(src)
        assert mod.test() == 6

    def test_array2_simple(self):
        src = """
        from array import array

        def test() -> int:
            a = array[int, 2](2, 3)
            a[0, 0] = 1
            a[0, 1] = 2
            a[0, 2] = 3
            a[1, 0] = 4
            a[1, 1] = 5
            a[1, 2] = 6
            return a[0, 0] + a[1, 2]
        """
        mod = self.compile(src)
        assert mod.test() == 7

    def test_len(self):
        src = """
        from array import array

        def test1() -> int:
            a = array[int, 1](3)
            return len(a)

        def test2() -> int:
            a = array[int, 2](4, 5)
            return len(a)
        """
        mod = self.compile(src)
        assert mod.test1() == 3
        assert mod.test2() == 4

    def test_from_buffer(self):
        src = """
        from array import array
        from unsafe import ptr, gc_alloc

        def alloc_buf(n: i32) -> ptr[i32]:
            return gc_alloc(i32)(n)

        def store(p: ptr[i32], i: i32, v: i32) -> None:
            p[i] = v

        def test(buf: ptr[i32], l: i32) -> int:
            a = array[int, 1].from_buffer(buf, l)
            return a[0] + a[1] + a[2]
        """
        mod = self.compile(src)
        buf = mod.alloc_buf(3)
        mod.store(buf, 0, 10)
        mod.store(buf, 1, 20)
        mod.store(buf, 2, 30)
        assert mod.test(buf, 3) == 60

    def test_zeros(self):
        src = """
        from array import zeros

        def test_len(n: i32) -> i32:
            a = zeros[f64](n)
            return len(a)

        def test_content(n: i32) -> f64:
            a = zeros[f64](n)
            return a[0] + a[1] + a[2]
        """
        mod = self.compile(src)
        assert mod.test_len(5) == 5
        assert mod.test_content(5) == 0
