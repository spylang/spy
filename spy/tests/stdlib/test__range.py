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

        def cont(it: range_iterator) -> bool:
            return it.__continue_iteration__()
        """
        mod = self.compile(src)
        it = mod.get_iter()

        assert it == (0, 3)
        assert mod.cont(it) == True
        it = mod.next(it)

        assert it == (1, 3)
        assert mod.cont(it) == True
        it = mod.next(it)

        assert it == (2, 3)
        assert mod.cont(it) == True
        it = mod.next(it)

        assert it == (3, 3)
        assert mod.cont(it) == False
