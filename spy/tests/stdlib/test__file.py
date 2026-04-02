import pytest

from spy.errors import SPyError
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

    def test_read(self):
        src = """
        from _file import open

        def do_read(fname: str) -> tuple[str, str]:
            f = open(fname)
            a = f.read(5)
            b = f.read()
            f.close()
            return a, b

        def do_read_closed(fname: str) -> str:
            f = open(fname)
            f.close()
            return f.read()
        """
        mod = self.compile(src)
        f = self.write_file("foo.txt", "hello world")
        tup = mod.do_read(str(f))
        assert tup == ("hello", " world")

        with SPyError.raises("W_ValueError", match="I/O operation on closed file"):
            mod.do_read_closed(str(f))

    def test_readline(self):
        src = """
        from _file import open

        def do_readline(fname: str) -> tuple[str, str, str]:
            f = open(fname)
            a = f.readline()
            b = f.readline()
            c = f.readline()
            f.close()
            return a, b, c

        def do_readline_closed(fname: str) -> str:
            f = open(fname)
            f.close()
            return f.readline()
        """
        mod = self.compile(src)
        f = self.write_file("foo.txt", "hello\nworld\n")
        assert mod.do_readline(str(f)) == ("hello\n", "world\n", "")

        with SPyError.raises("W_ValueError", match="I/O operation on closed file"):
            mod.do_readline_closed(str(f))
