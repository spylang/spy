import pytest
from spy.tests.support import CompilerTest


class TestDict(CompilerTest):

    def test_set_get_simple(self):
        src = """
        from dict import dict

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
        from dict import dict

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
        from dict import dict

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
        from dict import dict

        def test() -> int:
            d = dict[i32, i32]()
            return d[99]
        """
        mod = self.compile(src)
        with pytest.raises(Exception, match="KeyError"):
            mod.test()

    def test_many_inserts_and_lookup(self):
        src = """
        from dict import dict

        def test(n: i32) -> int:
            d = dict[i32, i32]()
            i = 1
            while i <= n:
                print("inserting " + str(i))
                d[i] = i
                i += 1
            print("done inserting")
            print("d[20]=" + str(d[20]))
            return d[n]
        """
        mod = self.compile(src)
        # assert mod.test(10) == 10
        # MIN_LOG_SIZE = 6 => 64 entries
        # MAX_FILL_RATIO = 2 / 3 => 43 entries to trigger resize
        assert mod.test(43) == 43
        # and 86 entries to trigger two resizes
        # assert mod.test(86) == 86

    def test_len_after_many_inserts(self):
        src = """
        from dict import dict

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
