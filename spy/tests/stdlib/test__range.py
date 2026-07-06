import pytest

from spy.tests.support import CompilerTest


class TestRange(CompilerTest):
    def test_simple(self):
        src = """
        from _range import range

        def make_range() -> range:
            return range(10)
        """
        mod = self.compile(src)
        r = mod.make_range()
        assert r.start == 0
        assert r.stop == 10

    def test_fastiter(self):
        src = """
        from _range import range, range_iterator

        def get_iter() -> range_iterator:
            r = range(3)
            return r.__fastiter__()

        def next(it: range_iterator) -> range_iterator:
            return it.__next__()

        def item(it: range_iterator) -> int:
            return it.__item__()

        def cont(it: range_iterator) -> bool:
            return it.__continue_iteration__()
        """
        mod = self.compile(src)
        it = mod.get_iter()

        assert it == (0, 3, 1)
        assert mod.cont(it) == True
        assert mod.item(it) == 0
        it = mod.next(it)

        assert it == (1, 3, 1)
        assert mod.cont(it) == True
        assert mod.item(it) == 1
        it = mod.next(it)

        assert it == (2, 3, 1)
        assert mod.cont(it) == True
        assert mod.item(it) == 2
        it = mod.next(it)

        assert it == (3, 3, 1)
        assert mod.cont(it) == False

    def test_misc(self):
        src = """
        from _range import range

        def tostr(r: range) -> str:
            s = ''
            for i in r:
                s += str(i) + ' '
            return s

        def fmt1(n: int) -> str:
            return tostr(range(n))

        def fmt2(a: int, b: int) -> str:
            return tostr(range(a, b))

        def fmt3(a: int, b: int, step: int) -> str:
            return tostr(range(a, b, step))
        """
        mod = self.compile(src)
        # Basic cases
        assert mod.fmt1(4) == "0 1 2 3 "
        assert mod.fmt2(3, 7) == "3 4 5 6 "

        # Step parameter
        assert mod.fmt3(0, 10, 2) == "0 2 4 6 8 "
        assert mod.fmt3(1, 10, 3) == "1 4 7 "
        assert mod.fmt3(5, 15, 4) == "5 9 13 "

        # Negative step
        assert mod.fmt3(10, 0, -1) == "10 9 8 7 6 5 4 3 2 1 "
        assert mod.fmt3(10, 0, -2) == "10 8 6 4 2 "
        assert mod.fmt3(5, -5, -3) == "5 2 -1 -4 "

        # Negative stop (empty ranges)
        assert mod.fmt1(-5) == ""
        assert mod.fmt2(0, -10) == ""
        assert mod.fmt2(5, 2) == ""

        # Edge cases
        assert mod.fmt1(0) == ""
        assert mod.fmt2(5, 5) == ""
        assert mod.fmt3(0, 0, 1) == ""
        assert mod.fmt3(10, 10, -1) == ""

    def test_contains(self):
        src = """
        from _range import range

        def range1_contains(x: int, n: int) -> bool:
            return x in range(n)

        def range3_contains(x: int, start: int, stop: int, step: int) -> bool:
            return x in range(start, stop, step)
        """
        mod = self.compile(src)

        assert mod.range1_contains(0, 3) == True
        assert mod.range1_contains(2, 3) == True
        assert mod.range1_contains(3, 3) == False
        assert mod.range1_contains(-1, 3) == False

        assert mod.range3_contains(4, 0, 10, 2) == True
        assert mod.range3_contains(3, 0, 10, 2) == False

        assert mod.range3_contains(1, 1, 10, 3) == True
        assert mod.range3_contains(4, 1, 10, 3) == True
        assert mod.range3_contains(2, 1, 10, 3) == False

        assert mod.range3_contains(10, 10, 0, -1) == True
        assert mod.range3_contains(5, 10, 0, -1) == True
        assert mod.range3_contains(0, 10, 0, -1) == False
        assert mod.range3_contains(8, 10, 0, -2) == True
        assert mod.range3_contains(7, 10, 0, -2) == False
