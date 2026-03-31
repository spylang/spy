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

    def test_fopen_fclose(self):
        src = """
        from posix import _fopen, _fclose

        def foo(fname: str) -> None:
            f = _fopen(fname)
            _fclose(f)
        """
        mod = self.compile(src)
        f = self.tmpdir.join("foo.txt")
        f.write("abcd123456f78")
        assert mod.foo(str(f)) is None
