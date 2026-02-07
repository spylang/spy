from spy.errors import SPyError
from spy.tests.support import CompilerTest, only_interp, skip_backends
from spy.vm.b import B


class TestDict(CompilerTest):
    def test_set_get_simple(self):
        src = """
        from _dict import dict

        def test() -> int:
            d = dict[i32, i32]()
            d[1] = 10
            d[2] = 20
            return d[1] + d[2]
        """
        mod = self.compile(src)
        assert mod.test() == 30

    def test_overwrite_value(self):
        src = """
        from _dict import dict

        def test() -> int:
            d = dict[i32, i32]()
            d[1] = 1
            d[1] = 3
            return d[1]
        """
        mod = self.compile(src)
        assert mod.test() == 3

    def test_len_and_no_growth_on_update(self):
        src = """
        from _dict import dict

        def test() -> int:
            d = dict[i32, i32]()
            d[1] = 1
            d[2] = 2
            d[3] = 3
            # updating an existing key should not change the length
            d[2] = 22
            return len(d)
        """
        mod = self.compile(src)
        assert mod.test() == 3

    def test_missing_key_raises(self):
        src = """
        from _dict import dict

        def test() -> int:
            d = dict[i32, i32]()
            return d[99]
        """
        mod = self.compile(src)
        with SPyError.raises("W_KeyError"):
            mod.test()

    def test_many_inserts_and_lookup(self):
        src = """
        from _dict import dict

        def test(n: i32) -> int:
            d = dict[i32, i32]()
            i = 1
            while i <= n:
                d[i] = i
                i += 1
            return d[n]
        """
        mod = self.compile(src)
        assert mod.test(10) == 10
        # MIN_LOG_SIZE = 6 => 64 entries
        # MAX_FILL_RATIO = 2 / 3 => 43 entries to trigger resize
        assert mod.test(43) == 43
        # and 86 entries to trigger two resizes
        assert mod.test(86) == 86

    def test_len_after_many_inserts(self):
        src = """
        from _dict import dict

        def test(n: i32) -> int:
            d = dict[i32, i32]()
            i = 0
            while i < n:
                d[i] = i
                i += 1
            return len(d)
        """
        mod = self.compile(src)
        assert mod.test(10) == 10

    def test_delete(self):
        src = """
        from _dict import dict

        def test() -> int:
            d = dict[i32, i32]()
            d[1] = 1
            # del d[1]
            d.__delitem__(1)
            return len(d)
        """
        mod = self.compile(src)
        assert mod.test() == 0

    def test_delete_twice_raises(self):
        src = """
        from _dict import dict

        def test() -> int:
            d = dict[i32, i32]()
            d[1] = 1
            # del d[1]
            d.__delitem__(1)
            d.__delitem__(1)
            return len(d)
        """
        mod = self.compile(src)
        with SPyError.raises("W_KeyError"):
            mod.test()

    def test_fastiter(self):
        src = """
        from _dict import dict

        def test() -> int:
            d = dict[i32, i32]()
            d[10] = -1
            d[20] = -1
            d[30] = -1
            it = d.__fastiter__()
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
        from _dict import dict

        def test() -> int:
            d = dict[i32, i32]()
            d[1] = -1
            d[2] = -1
            d[3] = -1
            d[4] = -1
            total = 0
            for x in d:
                total = total + x
            return total
        """
        mod = self.compile(src)
        assert mod.test() == 10

    def test_keys(self):
        src = """
        from _dict import dict

        def test() -> int:
            d = dict[i32, i32]()
            d[1] = -1
            d[2] = -1
            d[3] = -1
            d[4] = -1
            total = 0
            for x in d.keys():
                total = total + x
            return total
        """
        mod = self.compile(src)
        assert mod.test() == 10

    def test_contains(self):
        src = """
        from _dict import dict

        def test() -> bool:
            d = dict[i32, i32]()
            d[1] = 1
            return d.__contains__(1)
        """
        mod = self.compile(src)
        assert mod.test()

    def test_equal(self):
        src = """
        from _dict import dict

        def test_eq() -> bool:
            d1 = dict[i32, i32]()
            d1[1] = -1
            d1[2] = -1
            d1[3] = -1
            d2 = dict[i32, i32]()
            d2[1] = -1
            d2[2] = -1
            d2[3] = -1
            return d1 == d2

        def test_neq_value() -> bool:
            d1 = dict[i32, i32]()
            d1[1] = -1
            d1[2] = -1
            d1[3] = -1
            d2 = dict[i32, i32]()
            d2[1] = -1
            d2[2] = -1
            d2[3] = 0
            return d1 == d2

        def test_neq_missing_key() -> bool:
            d1 = dict[i32, i32]()
            d1[1] = -1
            d1[2] = -1
            d1[3] = -1
            d2 = dict[i32, i32]()
            d2[1] = -1
            d2[2] = -1
            return d1 == d2

        def test_neq_key() -> bool:
            d1 = dict[i32, i32]()
            d1[1] = -1
            d1[2] = -1
            d1[3] = -1
            d2 = dict[i32, i32]()
            d2[1] = -1
            d2[2] = -1
            d1[33] = -1
            return d1 == d2
        """
        mod = self.compile(src)
        assert mod.test_eq()
        assert not mod.test_neq_value()
        assert not mod.test_neq_missing_key()
        assert not mod.test_neq_key()

    def test_push(self):
        src = """
        from _dict import dict

        def test() -> int:
            d = dict[i32, i32]()
            d = d._push(1, 10)
            d = d._push(2, 20)
            d = d._push(3, 30)
            return d[1] + d[2] + d[3]
        """
        mod = self.compile(src)
        assert mod.test() == 60

    def test_literal_stdlib(self):
        mod = self.compile("""
        def foo() -> dict[i32, i32]:
            x = {0: 1, 50: 2, 30: 3}
            return x
        """)
        x = mod.foo()
        assert x == {0: 1, 50: 2, 30: 3}

    def test_literal_preserves_order(self):
        mod = self.compile("""
        def foo() -> dict[i32, i32]:
            return {1: 1, 2: 2, 3: 3}
        """)
        x = mod.foo()
        assert list(x.keys()) == [1, 2, 3]

    def test_empty_dict_literal(self):
        mod = self.compile("""
        def foo() ->i32:
            d: dict[i32, i32] = {}
            return len(d)
        """)
        assert mod.foo() == 0

    def test_literal_single_element(self):
        # useful for single element type
        mod = self.compile("""
        def foo() -> dict[i32, i32]:
            return {42: 100}
        """)
        x = mod.foo()
        assert x[42] == 100

    def test_literal_mixed_value_types_key_value(self):
        # useful for mixed type support
        # type of x must be i32
        # because union(i32, i32) = i32
        # However, mixed of different type like union(i32, f64) still not available yet
        # we need to implement interp_dict for type fallback like interp_list
        mod = self.compile("""
        def foo() -> dict[i32, i32]:
            x: i32 = 1
            y: i32 = 1000
            return {0: x, 1: y}
        """)
        x = mod.foo()
        assert x[0] == 1
        assert x[1] == 1000
