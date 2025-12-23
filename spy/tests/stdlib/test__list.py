import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest


class TestList(CompilerTest):
    def test_basic_operations(self):
        src = """
        from _list import list

        def test_empty() -> int:
            lst = list[int]()
            return len(lst)

        def test_append() -> int:
            lst = list[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            return len(lst)
        """
        mod = self.compile(src)
        assert mod.test_empty() == 0
        assert mod.test_append() == 3

    def test_list_of_string(self):
        src = """
        from _list import list

        def foo() -> str:
            lst = list[str]()
            lst.append("hello ")
            lst.append("world")
            return lst[0] + lst[1]
        """
        mod = self.compile(src)
        assert mod.foo() == "hello world"

    def test_getitem(self):
        src = """
        from _list import list

        def test_indexing() -> int:
            lst = list[int]()
            lst.append(100)
            lst.append(200)
            lst.append(300)
            return lst[1]

        def sum_list() -> int:
            lst = list[int]()
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

        def test_grow() -> int:
            lst = list[int]()
            i = 0
            while i < 10:
                lst.append(i)
                i = i + 1
            return lst[9]

        def test_f64() -> f64:
            lst = list[f64]()
            lst.append(1.5)
            lst.append(2.5)
            lst.append(3.5)
            return lst[1]

        def out_of_bounds() -> int:
            lst = list[int]()
            lst.append(42)
            return lst[5]
        """
        mod = self.compile(src)
        assert mod.test_indexing() == 200
        assert mod.sum_list() == 15
        assert mod.test_grow() == 9
        assert mod.test_f64() == 2.5
        with SPyError.raises("W_IndexError"):
            mod.out_of_bounds()

    def test_fastiter(self):
        src = """
        from _list import list

        def test() -> int:
            lst = list[int]()
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
        from _list import list

        def test() -> int:
            lst = list[int]()
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

    def test_setitem(self):
        src = """
        from _list import list

        def test_set() -> int:
            lst = list[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            lst[1] = 99
            return lst[1]

        def test_error() -> None:
            lst = list[int]()
            lst.append(10)
            lst[5] = 99
        """
        mod = self.compile(src)
        assert mod.test_set() == 99
        with SPyError.raises("W_IndexError"):
            mod.test_error()

    def test_pop(self):
        src = """
        from _list import list

        def test_pop() -> int:
            lst = list[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            x = lst.pop()
            y = len(lst)
            return x + y

        def test_empty() -> int:
            lst = list[int]()
            return lst.pop()
        """
        mod = self.compile(src)
        assert mod.test_pop() == 32  # 30 + 2
        with SPyError.raises("W_IndexError"):
            mod.test_empty()

    def test_insert(self):
        src = """
        from _list import list

        def test_middle() -> str:
            lst = list[int]()
            lst.append(10)
            lst.append(30)
            lst.insert(1, 20)

            s = ''
            for x in lst:
                s = s + str(x) + ' '
            return s

        def test_start() -> int:
            lst = list[int]()
            lst.append(20)
            lst.append(30)
            lst.insert(0, 10)
            return lst[0]

        def test_end() -> int:
            lst = list[int]()
            lst.append(10)
            lst.append(20)
            lst.insert(2, 30)
            return lst[2]
        """
        mod = self.compile(src)
        assert mod.test_middle() == "10 20 30 "
        assert mod.test_start() == 10
        assert mod.test_end() == 30

    def test_clear(self):
        src = """
        from _list import list

        def test_clear() -> int:
            lst = list[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            lst.clear()
            return len(lst)

        def test_reuse() -> int:
            lst = list[int]()
            lst.append(10)
            lst.append(20)
            lst.clear()
            lst.append(99)
            return lst[0]
        """
        mod = self.compile(src)
        assert mod.test_clear() == 0
        assert mod.test_reuse() == 99

    def test_negative_indexing(self):
        src = """
        from _list import list

        def test_last() -> int:
            lst = list[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            return lst[-1]

        def test_middle() -> int:
            lst = list[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            return lst[-2]

        def test_set() -> int:
            lst = list[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            lst[-1] = 99
            return lst[2]

        def test_error() -> int:
            lst = list[int]()
            lst.append(10)
            return lst[-5]
        """
        mod = self.compile(src)
        assert mod.test_last() == 30
        assert mod.test_middle() == 20
        assert mod.test_set() == 99
        with SPyError.raises("W_IndexError"):
            mod.test_error()

    def test_extend(self):
        src = """
        from _list import list

        def test_extend() -> str:
            lst1 = list[int]()
            lst1.append(10)
            lst1.append(20)

            lst2 = list[int]()
            lst2.append(30)
            lst2.append(40)

            lst1.extend(lst2)

            s = ''
            for x in lst1:
                s = s + str(x) + ' '
            return s

        def test_empty() -> int:
            lst1 = list[int]()
            lst1.append(10)

            lst2 = list[int]()

            lst1.extend(lst2)
            return len(lst1)
        """
        mod = self.compile(src)
        assert mod.test_extend() == "10 20 30 40 "
        assert mod.test_empty() == 1

    def test_copy(self):
        src = """
        from _list import list

        def test_independent() -> int:
            lst1 = list[int]()
            lst1.append(10)
            lst1.append(20)

            lst2 = lst1.copy()
            lst2[0] = 99

            return lst1[0]

        def test_values() -> int:
            lst1 = list[int]()
            lst1.append(10)
            lst1.append(20)
            lst1.append(30)

            lst2 = lst1.copy()
            return lst2[1]
        """
        mod = self.compile(src)
        assert mod.test_independent() == 10  # Original unchanged
        assert mod.test_values() == 20

    def test_add_operator(self):
        src = """
        from _list import list

        def test_concat() -> str:
            lst1 = list[int]()
            lst1.append(10)
            lst1.append(20)

            lst2 = list[int]()
            lst2.append(30)
            lst2.append(40)

            lst3 = lst1 + lst2

            s = ''
            for x in lst3:
                s = s + str(x) + ' '
            return s

        def test_unchanged() -> int:
            lst1 = list[int]()
            lst1.append(10)

            lst2 = list[int]()
            lst2.append(20)

            lst3 = lst1 + lst2
            return len(lst1)
        """
        mod = self.compile(src)
        assert mod.test_concat() == "10 20 30 40 "
        assert mod.test_unchanged() == 1  # lst1 unchanged

    def test_mul_operator(self):
        src = """
        from _list import list

        def test_repeat() -> str:
            lst = list[int]()
            lst.append(10)
            lst.append(20)

            lst2 = lst * 3

            s = ''
            for x in lst2:
                s = s + str(x) + ' '
            return s

        def test_zero() -> int:
            lst = list[int]()
            lst.append(10)
            lst.append(20)

            lst2 = lst * 0
            return len(lst2)

        def test_one() -> int:
            lst = list[int]()
            lst.append(10)
            lst.append(20)

            lst2 = lst * 1
            return lst2[1]
        """
        mod = self.compile(src)
        assert mod.test_repeat() == "10 20 10 20 10 20 "
        assert mod.test_zero() == 0
        assert mod.test_one() == 20

    def test_index(self):
        src = """
        from _list import list

        def test_middle() -> int:
            lst = list[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            return lst.index(20)

        def test_first() -> int:
            lst = list[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            return lst.index(10)

        def test_last() -> int:
            lst = list[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            return lst.index(30)

        def test_not_found() -> int:
            lst = list[int]()
            lst.append(10)
            lst.append(20)
            return lst.index(99)

        def test_duplicate() -> int:
            lst = list[int]()
            lst.append(10)
            lst.append(20)
            lst.append(10)
            return lst.index(10)
        """
        mod = self.compile(src)
        assert mod.test_middle() == 1
        assert mod.test_first() == 0
        assert mod.test_last() == 2
        with SPyError.raises("W_ValueError"):
            mod.test_not_found()
        assert mod.test_duplicate() == 0  # Returns first occurrence

    def test_count(self):
        src = """
        from _list import list

        def test_multiple() -> int:
            lst = list[int]()
            lst.append(10)
            lst.append(20)
            lst.append(10)
            lst.append(30)
            lst.append(10)
            return lst.count(10)

        def test_zero() -> int:
            lst = list[int]()
            lst.append(10)
            lst.append(20)
            return lst.count(99)

        def test_one() -> int:
            lst = list[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            return lst.count(20)

        def test_empty() -> int:
            lst = list[int]()
            return lst.count(10)
        """
        mod = self.compile(src)
        assert mod.test_multiple() == 3
        assert mod.test_zero() == 0
        assert mod.test_one() == 1
        assert mod.test_empty() == 0

    def test_remove(self):
        src = """
        from _list import list

        def test_middle() -> str:
            lst = list[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            lst.remove(20)

            s = ''
            for x in lst:
                s = s + str(x) + ' '
            return s

        def test_first() -> int:
            lst = list[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            lst.remove(10)
            return lst[0]

        def test_last() -> int:
            lst = list[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            lst.remove(30)
            return len(lst)

        def test_duplicate() -> str:
            lst = list[int]()
            lst.append(10)
            lst.append(20)
            lst.append(10)
            lst.append(30)
            lst.remove(10)

            s = ''
            for x in lst:
                s = s + str(x) + ' '
            return s

        def test_not_found() -> None:
            lst = list[int]()
            lst.append(10)
            lst.append(20)
            lst.remove(99)

        def test_length() -> int:
            lst = list[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            lst.remove(20)
            return len(lst)
        """
        mod = self.compile(src)
        assert mod.test_middle() == "10 30 "
        assert mod.test_first() == 20
        assert mod.test_last() == 2
        assert mod.test_duplicate() == "20 10 30 "  # Only first occurrence removed
        with SPyError.raises("W_ValueError"):
            mod.test_not_found()
        assert mod.test_length() == 2

    def test_eq(self):
        src = """
        from _list import list

        def test_equal() -> bool:
            lst1 = list[int]()
            lst1.append(10)
            lst1.append(20)
            lst1.append(30)

            lst2 = list[int]()
            lst2.append(10)
            lst2.append(20)
            lst2.append(30)

            return lst1 == lst2

        def test_empty() -> bool:
            lst1 = list[int]()
            lst2 = list[int]()
            return lst1 == lst2

        def test_diff_length() -> bool:
            lst1 = list[int]()
            lst1.append(10)
            lst1.append(20)

            lst2 = list[int]()
            lst2.append(10)
            lst2.append(20)
            lst2.append(30)

            return lst1 == lst2

        def test_diff_elems() -> bool:
            lst1 = list[int]()
            lst1.append(10)
            lst1.append(20)
            lst1.append(30)

            lst2 = list[int]()
            lst2.append(10)
            lst2.append(99)
            lst2.append(30)

            return lst1 == lst2

        def test_single_same() -> bool:
            lst1 = list[int]()
            lst1.append(42)

            lst2 = list[int]()
            lst2.append(42)

            return lst1 == lst2

        def test_single_diff() -> bool:
            lst1 = list[int]()
            lst1.append(42)

            lst2 = list[int]()
            lst2.append(99)

            return lst1 == lst2

        def test_after_mutations() -> bool:
            lst1 = list[int]()
            lst1.append(10)
            lst1.append(20)
            lst1.append(30)
            lst1.remove(20)

            lst2 = list[int]()
            lst2.append(10)
            lst2.append(30)

            return lst1 == lst2

        def test_f64() -> bool:
            lst1 = list[f64]()
            lst1.append(1.5)
            lst1.append(2.5)

            lst2 = list[f64]()
            lst2.append(1.5)
            lst2.append(2.5)

            return lst1 == lst2
        """
        mod = self.compile(src)
        assert mod.test_equal() == True
        assert mod.test_empty() == True
        assert mod.test_diff_length() == False
        assert mod.test_diff_elems() == False
        assert mod.test_single_same() == True
        assert mod.test_single_diff() == False
        assert mod.test_after_mutations() == True
        assert mod.test_f64() == True
