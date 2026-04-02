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

    def test_write(self):
        src = """
        from _file import open

        def do_write(fname: str) -> None:
            f = open(fname, 'w')
            f.write('hello world')
            f.close()

        def do_write_closed(fname: str) -> None:
            f = open(fname, 'w')
            f.close()
            f.write('hello')
        """
        mod = self.compile(src)
        f = self.tmpdir.join("out.txt")
        mod.do_write(str(f))
        assert f.read() == "hello world"

        with SPyError.raises("W_ValueError", match="I/O operation on closed file"):
            mod.do_write_closed(str(f))

    def test_iter(self):
        src = r"""
        from _file import open

        def foo(fname: str) -> str:
            f = open(fname)
            result = ''
            for line in f:
                if result != '':
                    result = result + '---\n'
                result = result + line
            f.close()
            return result
        """
        mod = self.compile(src)
        f = self.write_file("foo.txt", "aaa\nbbb\nccc\n")
        s = mod.foo(str(f))
        assert s.splitlines() == [
            "aaa",
            "---",
            "bbb",
            "---",
            "ccc",
        ]

    def test_tell_seek(self):
        src = """
        from posix import SEEK_SET, SEEK_CUR, SEEK_END
        from _file import open

        def do_tell_seek(fname: str) -> tuple[i32, i32, str, str, str]:
            f = open(fname)
            pos0 = f.tell()
            f.read(5)
            pos1 = f.tell()
            f.seek(0)
            a = f.read(5)
            f.seek(6)
            b = f.read()
            f.seek(-5, SEEK_END)
            c = f.read()
            f.close()
            return pos0, pos1, a, b, c

        def do_tell_closed(fname: str) -> i32:
            f = open(fname)
            f.close()
            return f.tell()

        def do_seek_closed(fname: str) -> None:
            f = open(fname)
            f.close()
            f.seek(0)
        """
        mod = self.compile(src)
        f = self.write_file("foo.txt", "hello world")
        assert mod.do_tell_seek(str(f)) == (0, 5, "hello", "world", "world")

        with SPyError.raises("W_ValueError", match="I/O operation on closed file"):
            mod.do_tell_closed(str(f))

        with SPyError.raises("W_ValueError", match="I/O operation on closed file"):
            mod.do_seek_closed(str(f))

    def test_flush(self):
        src = """
        from _file import open

        def do_flush(wname: str, rname: str) -> str:
            wf = open(wname, 'w')
            wf.write('hello')
            wf.flush()
            rf = open(rname)
            content = rf.read()
            rf.close()
            wf.close()
            return content

        def do_flush_closed(fname: str) -> None:
            f = open(fname, 'w')
            f.close()
            f.flush()
        """
        mod = self.compile(src)
        f = self.tmpdir.join("out.txt")
        assert mod.do_flush(str(f), str(f)) == "hello"

        with SPyError.raises("W_ValueError", match="I/O operation on closed file"):
            mod.do_flush_closed(str(f))

    def test_fileno_isatty(self):
        src = """
        from _file import open

        def do_fileno(fname: str) -> bool:
            f = open(fname)
            fd = f.fileno()
            f.close()
            return fd >= 0

        def do_isatty(fname: str) -> bool:
            f = open(fname)
            res = f.isatty()
            f.close()
            return res

        def do_fileno_closed(fname: str) -> i32:
            f = open(fname)
            f.close()
            return f.fileno()

        def do_isatty_closed(fname: str) -> bool:
            f = open(fname)
            f.close()
            return f.isatty()
        """
        mod = self.compile(src)
        f = self.write_file("foo.txt", "hello")
        assert mod.do_fileno(str(f)) == True
        assert mod.do_isatty(str(f)) == False

        with SPyError.raises("W_ValueError", match="I/O operation on closed file"):
            mod.do_fileno_closed(str(f))

        with SPyError.raises("W_ValueError", match="I/O operation on closed file"):
            mod.do_isatty_closed(str(f))

    def test_writelines(self):
        src = """
        from _file import open

        def do_writelines(fname: str) -> None:
            f = open(fname, 'w')
            f.writelines(['hello', ' ', 'world'])
            f.close()

        def do_writelines_closed(fname: str) -> None:
            f = open(fname, 'w')
            f.close()
            f.writelines(['hello'])
        """
        mod = self.compile(src)
        f = self.tmpdir.join("out.txt")
        mod.do_writelines(str(f))
        assert f.read() == "hello world"

        with SPyError.raises("W_ValueError", match="I/O operation on closed file"):
            mod.do_writelines_closed(str(f))
