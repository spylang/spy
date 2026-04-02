import pytest

from spy.tests.support import CompilerTest


class TestFile(CompilerTest):
    def test_open_close(self):
        src = """
        from _file import open

        def foo(fname: str) -> tuple[str, str]:
            f = open(fname)
            s0 = str(f)
            f.close()
            s1 = str(f)
            return s0, s1
        """
        mod = self.compile(src)
        f = self.write_file("foo.txt", "hello")
        tup = mod.foo(str(f))
        s0 = tup._item0
        s1 = tup._item1
        assert s0 == f"<spy open file '{f}', mode 'r'>"
        assert s1 == f"<spy closed file '{f}', mode 'r'>"
