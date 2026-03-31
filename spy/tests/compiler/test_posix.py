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
            f = _fopen(fname)
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
            f = _fopen(fname)
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
            f = _fopen(fname)
            content = _freadall(f)
            _fclose(f)
            return content

        def read_then_readall(fname: str) -> tuple[str, str, str]:
            f = _fopen(fname)
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
            f = _fopen(fname)
            content = __freadall_chunked(f)
            _fclose(f)
            return content
        """
        mod = self.compile(src)
        f = self.tmpdir.join("foo.txt")
        f.write("hello world")
        assert mod.foo(str(f)) == "hello world"
