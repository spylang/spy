import pytest

from spy.tests.support import CompilerTest


class TestFile(CompilerTest):
    def test_open_close(self):
        src = """
        from _file import open

        def foo(fname: str) -> str:
            f = open(fname)
            s = str(f)
            f.close()
            return s
        """
        mod = self.compile(src)
        f = self.write_file("foo.txt", "hello")
        s = mod.foo(str(f))
        assert s == f"<spy file '{f}', mode 'r'>"
