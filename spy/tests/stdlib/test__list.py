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

    def test_setitem(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            lst[1] = 99
            return lst[1]
        """
        mod = self.compile(src)
        assert mod.test() == 99

    def test_setitem_error(self):
        src = """
        from _list import List

        def test() -> None:
            lst = List[int]()
            lst.append(10)
            lst[5] = 99
        """
        mod = self.compile(src)
        with SPyError.raises('W_IndexError'):
            mod.test()

    def test_pop(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            x = lst.pop()
            y = len(lst)
            return x + y
        """
        mod = self.compile(src)
        assert mod.test() == 32  # 30 + 2

    def test_pop_empty(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            return lst.pop()
        """
        mod = self.compile(src)
        with SPyError.raises('W_IndexError'):
            mod.test()

    def test_insert(self):
        src = """
        from _list import List

        def test() -> str:
            lst = List[int]()
            lst.append(10)
            lst.append(30)
            lst.insert(1, 20)

            s = ''
            for x in lst:
                s = s + str(x) + ' '
            return s
        """
        mod = self.compile(src)
        assert mod.test() == '10 20 30 '

    def test_insert_at_start(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            lst.append(20)
            lst.append(30)
            lst.insert(0, 10)
            return lst[0]
        """
        mod = self.compile(src)
        assert mod.test() == 10

    def test_insert_at_end(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            lst.append(10)
            lst.append(20)
            lst.insert(2, 30)
            return lst[2]
        """
        mod = self.compile(src)
        assert mod.test() == 30

    def test_clear(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            lst.clear()
            return len(lst)
        """
        mod = self.compile(src)
        assert mod.test() == 0

    def test_clear_and_reuse(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            lst.append(10)
            lst.append(20)
            lst.clear()
            lst.append(99)
            return lst[0]
        """
        mod = self.compile(src)
        assert mod.test() == 99

    def test_negative_index_get(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            return lst[-1]
        """
        mod = self.compile(src)
        assert mod.test() == 30

    def test_negative_index_middle(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            return lst[-2]
        """
        mod = self.compile(src)
        assert mod.test() == 20

    def test_negative_index_set(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            lst[-1] = 99
            return lst[2]
        """
        mod = self.compile(src)
        assert mod.test() == 99

    def test_negative_index_error(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            lst.append(10)
            return lst[-5]
        """
        mod = self.compile(src)
        with SPyError.raises('W_IndexError'):
            mod.test()

    def test_extend(self):
        src = """
        from _list import List

        def test() -> str:
            lst1 = List[int]()
            lst1.append(10)
            lst1.append(20)

            lst2 = List[int]()
            lst2.append(30)
            lst2.append(40)

            lst1.extend(lst2)

            s = ''
            for x in lst1:
                s = s + str(x) + ' '
            return s
        """
        mod = self.compile(src)
        assert mod.test() == '10 20 30 40 '

    def test_extend_empty(self):
        src = """
        from _list import List

        def test() -> int:
            lst1 = List[int]()
            lst1.append(10)

            lst2 = List[int]()

            lst1.extend(lst2)
            return len(lst1)
        """
        mod = self.compile(src)
        assert mod.test() == 1

    def test_copy(self):
        src = """
        from _list import List

        def test() -> int:
            lst1 = List[int]()
            lst1.append(10)
            lst1.append(20)

            lst2 = lst1.copy()
            lst2[0] = 99

            return lst1[0]
        """
        mod = self.compile(src)
        assert mod.test() == 10  # Original unchanged

    def test_copy_values(self):
        src = """
        from _list import List

        def test() -> int:
            lst1 = List[int]()
            lst1.append(10)
            lst1.append(20)
            lst1.append(30)

            lst2 = lst1.copy()
            return lst2[1]
        """
        mod = self.compile(src)
        assert mod.test() == 20

    def test_add_operator(self):
        src = """
        from _list import List

        def test() -> str:
            lst1 = List[int]()
            lst1.append(10)
            lst1.append(20)

            lst2 = List[int]()
            lst2.append(30)
            lst2.append(40)

            lst3 = lst1 + lst2

            s = ''
            for x in lst3:
                s = s + str(x) + ' '
            return s
        """
        mod = self.compile(src)
        assert mod.test() == '10 20 30 40 '

    def test_add_operator_original_unchanged(self):
        src = """
        from _list import List

        def test() -> int:
            lst1 = List[int]()
            lst1.append(10)

            lst2 = List[int]()
            lst2.append(20)

            lst3 = lst1 + lst2
            return len(lst1)
        """
        mod = self.compile(src)
        assert mod.test() == 1  # lst1 unchanged

    def test_mul_operator(self):
        src = """
        from _list import List

        def test() -> str:
            lst = List[int]()
            lst.append(10)
            lst.append(20)

            lst2 = lst * 3

            s = ''
            for x in lst2:
                s = s + str(x) + ' '
            return s
        """
        mod = self.compile(src)
        assert mod.test() == '10 20 10 20 10 20 '

    def test_mul_operator_zero(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            lst.append(10)
            lst.append(20)

            lst2 = lst * 0
            return len(lst2)
        """
        mod = self.compile(src)
        assert mod.test() == 0

    def test_mul_operator_one(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            lst.append(10)
            lst.append(20)

            lst2 = lst * 1
            return lst2[1]
        """
        mod = self.compile(src)
        assert mod.test() == 20

    def test_index(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            return lst.index(20)
        """
        mod = self.compile(src)
        assert mod.test() == 1

    def test_index_first(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            return lst.index(10)
        """
        mod = self.compile(src)
        assert mod.test() == 0

    def test_index_last(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            return lst.index(30)
        """
        mod = self.compile(src)
        assert mod.test() == 2

    def test_index_not_found(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            lst.append(10)
            lst.append(20)
            return lst.index(99)
        """
        mod = self.compile(src)
        with SPyError.raises('W_ValueError'):
            mod.test()

    def test_index_duplicate(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            lst.append(10)
            lst.append(20)
            lst.append(10)
            return lst.index(10)
        """
        mod = self.compile(src)
        assert mod.test() == 0  # Returns first occurrence

    def test_count(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            lst.append(10)
            lst.append(20)
            lst.append(10)
            lst.append(30)
            lst.append(10)
            return lst.count(10)
        """
        mod = self.compile(src)
        assert mod.test() == 3

    def test_count_zero(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            lst.append(10)
            lst.append(20)
            return lst.count(99)
        """
        mod = self.compile(src)
        assert mod.test() == 0

    def test_count_one(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            return lst.count(20)
        """
        mod = self.compile(src)
        assert mod.test() == 1

    def test_count_empty(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            return lst.count(10)
        """
        mod = self.compile(src)
        assert mod.test() == 0

    def test_remove(self):
        src = """
        from _list import List

        def test() -> str:
            lst = List[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            lst.remove(20)

            s = ''
            for x in lst:
                s = s + str(x) + ' '
            return s
        """
        mod = self.compile(src)
        assert mod.test() == '10 30 '

    def test_remove_first(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            lst.remove(10)
            return lst[0]
        """
        mod = self.compile(src)
        assert mod.test() == 20

    def test_remove_last(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            lst.remove(30)
            return len(lst)
        """
        mod = self.compile(src)
        assert mod.test() == 2

    def test_remove_duplicate(self):
        src = """
        from _list import List

        def test() -> str:
            lst = List[int]()
            lst.append(10)
            lst.append(20)
            lst.append(10)
            lst.append(30)
            lst.remove(10)

            s = ''
            for x in lst:
                s = s + str(x) + ' '
            return s
        """
        mod = self.compile(src)
        assert mod.test() == '20 10 30 '  # Only first occurrence removed

    def test_remove_not_found(self):
        src = """
        from _list import List

        def test() -> None:
            lst = List[int]()
            lst.append(10)
            lst.append(20)
            lst.remove(99)
        """
        mod = self.compile(src)
        with SPyError.raises('W_ValueError'):
            mod.test()

    def test_remove_and_length(self):
        src = """
        from _list import List

        def test() -> int:
            lst = List[int]()
            lst.append(10)
            lst.append(20)
            lst.append(30)
            lst.remove(20)
            return len(lst)
        """
        mod = self.compile(src)
        assert mod.test() == 2

    def test_eq_equal_lists(self):
        src = """
        from _list import List

        def test() -> bool:
            lst1 = List[int]()
            lst1.append(10)
            lst1.append(20)
            lst1.append(30)

            lst2 = List[int]()
            lst2.append(10)
            lst2.append(20)
            lst2.append(30)

            return lst1 == lst2
        """
        mod = self.compile(src)
        assert mod.test() == True

    def test_eq_empty_lists(self):
        src = """
        from _list import List

        def test() -> bool:
            lst1 = List[int]()
            lst2 = List[int]()
            return lst1 == lst2
        """
        mod = self.compile(src)
        assert mod.test() == True

    def test_eq_different_length(self):
        src = """
        from _list import List

        def test() -> bool:
            lst1 = List[int]()
            lst1.append(10)
            lst1.append(20)

            lst2 = List[int]()
            lst2.append(10)
            lst2.append(20)
            lst2.append(30)

            return lst1 == lst2
        """
        mod = self.compile(src)
        assert mod.test() == False

    def test_eq_different_elements(self):
        src = """
        from _list import List

        def test() -> bool:
            lst1 = List[int]()
            lst1.append(10)
            lst1.append(20)
            lst1.append(30)

            lst2 = List[int]()
            lst2.append(10)
            lst2.append(99)
            lst2.append(30)

            return lst1 == lst2
        """
        mod = self.compile(src)
        assert mod.test() == False

    def test_eq_single_element(self):
        src = """
        from _list import List

        def test() -> bool:
            lst1 = List[int]()
            lst1.append(42)

            lst2 = List[int]()
            lst2.append(42)

            return lst1 == lst2
        """
        mod = self.compile(src)
        assert mod.test() == True

    def test_eq_single_element_different(self):
        src = """
        from _list import List

        def test() -> bool:
            lst1 = List[int]()
            lst1.append(42)

            lst2 = List[int]()
            lst2.append(99)

            return lst1 == lst2
        """
        mod = self.compile(src)
        assert mod.test() == False

    def test_eq_after_mutations(self):
        src = """
        from _list import List

        def test() -> bool:
            lst1 = List[int]()
            lst1.append(10)
            lst1.append(20)
            lst1.append(30)
            lst1.remove(20)

            lst2 = List[int]()
            lst2.append(10)
            lst2.append(30)

            return lst1 == lst2
        """
        mod = self.compile(src)
        assert mod.test() == True

    def test_eq_f64_type(self):
        src = """
        from _list import List

        def test() -> bool:
            lst1 = List[f64]()
            lst1.append(1.5)
            lst1.append(2.5)

            lst2 = List[f64]()
            lst2.append(1.5)
            lst2.append(2.5)

            return lst1 == lst2
        """
        mod = self.compile(src)
        assert mod.test() == True
