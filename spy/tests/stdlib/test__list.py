import pytest
from spy.tests.support import CompilerTest
from spy.errors import SPyError

class TestList(CompilerTest):

    def test_empty_list(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            return len(lst)
        """
        mod = self.compile(src)
        assert mod.test() == 0

    def test_append_and_len(self):
        src = """
        from _list import List

        def test_append() -> int:
            lst = List[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            return len(lst)
        """
        mod = self.compile(src)
        assert mod.test_append() == 3

    def test_getitem(self):
        src = """
        from _list import List

        def test_indexing() -> int:
            lst = List[int]()
            lst.append(100)
            lst.append(200)
            lst.append(300)
            return lst[1]
        """
        mod = self.compile(src)
        assert mod.test_indexing() == 200

    def test_multiple_elements(self):
        src = """
        from _list import List

        def sum_list() -> int:
            lst = List[int]()
            lst.append(1)
            lst.append(2)
            lst.append(3)
            lst.append(4)
            lst.append(5)

            total = 0
            i = 0
            while i < len(lst):
                total = total + lst[i]
                i = i + 1
            return total
        """
        mod = self.compile(src)
        assert mod.sum_list() == 15

    def test_grow_capacity(self):
        src = """
        from _list import List

        def test_grow() -> int:
            lst = List[int]()
            i = 0
            while i < 10:
                lst.append(i)
                i = i + 1
            return lst[9]
        """
        mod = self.compile(src)
        assert mod.test_grow() == 9

    def test_generic_type(self):
        src = """
        from _list import List

        def test_f64_list() -> f64:
            lst = List[f64]()
            lst.append(1.5)
            lst.append(2.5)
            lst.append(3.5)
            return lst[1]
        """
        mod = self.compile(src)
        assert mod.test_f64_list() == 2.5

    def test_index_error(self):
        src = """
        from _list import List

        def out_of_bounds() -> int:
            lst = List[int]()
            lst.append(42)
            return lst[5]
        """
        mod = self.compile(src)
        with SPyError.raises('W_IndexError'):
            mod.out_of_bounds()

    def test_fastiter(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)

            it = lst.__fastiter__()
            total = 0
            while it.__continue_iteration__():
                total = total + it.__item__()
                it = it.__next__()
            return total
        """
        mod = self.compile(src)
        assert mod.test() == 60

    def test_for_loop(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            lst.append(1)
            lst.append(2)
            lst.append(3)
            lst.append(4)

            total = 0
            for x in lst:
                total = total + x
            return total
        """
        mod = self.compile(src)
        assert mod.test() == 10

    def test_for_loop_string_concat(self):
        src = """
        from _list import List

        def test() -> str:
            lst = List[int]()
            lst.append(5)
            lst.append(10)
            lst.append(15)

            s = ''
            for x in lst:
                s = s + str(x) + ' '
            return s
        """
        mod = self.compile(src)
        assert mod.test() == '5 10 15 '
