from spy.errors import SPyError
from spy.tests.support import CompilerTest


class TestPosix(CompilerTest):
    def test_get_terminal_size(self):
        mod = self.compile("""
        from posix import TerminalSize, get_terminal_size

        def foo() -> str:
            size: TerminalSize = get_terminal_size()
            return str(size.lines) + " " + str(size.columns)
        """)
        result = mod.foo()
        parts = result.split()
        assert len(parts) == 2
        lines = int(parts[0])
        columns = int(parts[1])
        # When running in pytest without a terminal, we get fallback values
        assert columns >= 80
        assert lines >= 24

    def test_fopen_fread(self):
        src = """
        from posix import _fopen, _fread, _fclose

        def foo(fname: str) -> tuple[str, str]:
            f = _fopen(fname, 'r')
            a = _fread(f, 4)
            b = _fread(f, 8)
            _fclose(f)
            return a, b
        """
        mod = self.compile(src)
        f = self.tmpdir.join("foo.txt")
        f.write("abcd12345678")
        tup = mod.foo(str(f))
        assert tup == ("abcd", "12345678")

    def test_fread_short_read(self):
        src = """
        from posix import _fopen, _fread, _fclose

        def foo(fname: str) -> tuple[str, str]:
            f = _fopen(fname, 'r')
            a = _fread(f, 100)
            b = _fread(f, 10)
            _fclose(f)
            return a, b
        """
        mod = self.compile(src)
        f = self.tmpdir.join("foo.txt")
        f.write("hello")
        tup = mod.foo(str(f))
        assert tup == ("hello", "")

    def test_freadall(self):
        src = """
        from posix import _fopen, _fread, _freadall, _fclose

        def readall(fname: str) -> str:
            f = _fopen(fname, 'r')
            content = _freadall(f)
            _fclose(f)
            return content

        def read_then_readall(fname: str) -> tuple[str, str, str]:
            f = _fopen(fname, 'r')
            head = _fread(f, 5)
            rest = _freadall(f)
            empty = _freadall(f)
            _fclose(f)
            return head, rest, empty
        """
        mod = self.compile(src)
        f = self.tmpdir.join("foo.txt")
        f.write("hello world")
        assert mod.readall(str(f)) == "hello world"
        tup = mod.read_then_readall(str(f))
        assert tup == ("hello", " world", "")

    def test_freadall_chunked(self):
        src = """
        from posix import _fopen, __freadall_chunked, _fclose

        def foo(fname: str) -> str:
            f = _fopen(fname, 'r')
            content = __freadall_chunked(f)
            _fclose(f)
            return content
        """
        mod = self.compile(src)
        f = self.tmpdir.join("foo.txt")
        f.write("hello world")
        assert mod.foo(str(f)) == "hello world"

    def test_freadline(self):
        src = """
        from posix import _fopen, _freadline, _fclose

        def foo(fname: str) -> tuple[str, str, str]:
            f = _fopen(fname, 'r')
            a = _freadline(f)
            b = _freadline(f)
            c = _freadline(f)
            _fclose(f)
            return a, b, c
        """
        mod = self.compile(src)
        f = self.tmpdir.join("foo.txt")
        f.write("hello\nworld\n")
        tup = mod.foo(str(f))
        assert tup == ("hello\n", "world\n", "")

    def test_fwrite(self):
        src = """
        from posix import _fopen, _fwrite, _fclose

        def foo(fname: str) -> None:
            f = _fopen(fname, 'w')
            _fwrite(f, 'hello world')
            _fclose(f)
        """
        mod = self.compile(src)
        f = self.tmpdir.join("out.txt")
        mod.foo(str(f))
        assert f.read() == "hello world"

    def test_fopen_append(self):
        src = """
        from posix import _fopen, _fwrite, _fclose

        def foo(fname: str) -> None:
            f = _fopen(fname, 'a')
            _fwrite(f, ' world')
            _fclose(f)
        """
        mod = self.compile(src)
        f = self.tmpdir.join("out.txt")
        f.write("hello")
        mod.foo(str(f))
        assert f.read() == "hello world"

    def test_fopen_invalid_mode(self):
        src = """
        from posix import _fopen, _fclose

        def foo(fname: str) -> None:
            f = _fopen(fname, 'x')
            _fclose(f)
        """
        mod = self.compile(src)
        f = self.tmpdir.join("foo.txt")
        f.write("hello")
        with SPyError.raises("W_PanicError", match="invalid mode"):
            mod.foo(str(f))

    def test_ftell(self):
        src = """
        from posix import _fopen, _fread, _ftell, _fclose

        def foo(fname: str) -> tuple[i32, i32]:
            f = _fopen(fname, 'r')
            pos0 = _ftell(f)
            _fread(f, 5)
            pos1 = _ftell(f)
            _fclose(f)
            return pos0, pos1
        """
        mod = self.compile(src)
        f = self.tmpdir.join("foo.txt")
        f.write("hello world")
        assert mod.foo(str(f)) == (0, 5)

    def test_fseek(self):
        src = """
        from posix import (
            _fopen, _fread, _fseek, _ftell, _fclose,
            SEEK_SET, SEEK_CUR, SEEK_END,
        )

        def foo(fname: str) -> tuple[str, str, str]:
            f = _fopen(fname, 'r')
            _fseek(f, 6, SEEK_SET)
            a = _fread(f, 5)
            _fseek(f, -5, SEEK_END)
            b = _fread(f, 5)
            _fseek(f, -3, SEEK_CUR)
            c = _fread(f, 3)
            _fclose(f)
            return a, b, c
        """
        mod = self.compile(src)
        f = self.tmpdir.join("foo.txt")
        f.write("hello world")
        assert mod.foo(str(f)) == ("world", "world", "rld")

    def test_fopen_mode_read_write(self):
        src = """
        from posix import _fopen, _fread, _fwrite, _fseek, _fclose, SEEK_SET

        def foo(fname: str) -> str:
            f = _fopen(fname, 'r+')
            _fwrite(f, 'HELLO')
            _fseek(f, 0, SEEK_SET)
            content = _fread(f, 11)
            _fclose(f)
            return content
        """
        mod = self.compile(src)
        f = self.tmpdir.join("out.txt")
        f.write("hello world")
        assert mod.foo(str(f)) == "HELLO world"

    def test_FILE_eq_self(self):
        src = """
        from posix import _fopen, _fclose, _FILE

        def foo(fname: str) -> bool:
            f: _FILE = _fopen(fname, 'r')
            res = f == f
            _fclose(f)
            return res
        """
        mod = self.compile(src)
        f = self.tmpdir.join("foo.txt")
        f.write("hello")
        assert mod.foo(str(f)) == True

    def test_FILE_ne_NULL(self):
        src = """
        from posix import _fopen, _fclose, _FILE, _FILE_NULL

        def foo(fname: str) -> bool:
            f: _FILE = _fopen(fname, 'r')
            res = f == _FILE_NULL
            _fclose(f)
            return res
        """
        mod = self.compile(src)
        f = self.tmpdir.join("foo.txt")
        f.write("hello")
        assert mod.foo(str(f)) == False

    def test_fflush(self):
        src = """
        from posix import _fopen, _fwrite, _fflush, _fclose, _fread

        def foo(wname: str, rname: str) -> str:
            wf = _fopen(wname, 'w')
            _fwrite(wf, 'hello')
            _fflush(wf)
            rf = _fopen(rname, 'r')
            content = _fread(rf, 100)
            _fclose(rf)
            _fclose(wf)
            return content
        """
        mod = self.compile(src)
        f = self.tmpdir.join("out.txt")
        assert mod.foo(str(f), str(f)) == "hello"

    def test_fopen_mode_read_append(self):
        src = """
        from posix import _fopen, _fread, _fwrite, _fseek, _fclose, SEEK_SET

        def foo(fname: str) -> str:
            f = _fopen(fname, 'a+')
            _fwrite(f, ' world')
            _fseek(f, 0, SEEK_SET)
            content = _fread(f, 11)
            _fclose(f)
            return content
        """
        mod = self.compile(src)
        f = self.tmpdir.join("out.txt")
        f.write("hello")
        assert mod.foo(str(f)) == "hello world"

    def test_fileno(self):
        src = """
        from posix import _fopen, _fclose, _fileno

        def foo(fname: str) -> bool:
            f = _fopen(fname, 'r')
            fd = _fileno(f)
            _fclose(f)
            return fd >= 0
        """
        mod = self.compile(src)
        f = self.tmpdir.join("foo.txt")
        f.write("hello")
        assert mod.foo(str(f)) == True

    def test_isatty(self):
        src = """
        from posix import _fopen, _fclose, _fileno, _isatty

        def foo(fname: str) -> bool:
            f = _fopen(fname, 'r')
            fd = _fileno(f)
            res = _isatty(fd)
            _fclose(f)
            return res
        """
        mod = self.compile(src)
        f = self.tmpdir.join("foo.txt")
        f.write("hello")
        assert mod.foo(str(f)) == False
