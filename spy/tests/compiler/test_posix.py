import os

from spy.errors import SPyError
from spy.tests.support import CompilerTest, skip_backends


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

    @skip_backends("C", reason="WASI sandbox cannot access host filesystem paths")
    def test_open_read(self, tmp_path):
        fpath = tmp_path / "hello.txt"
        fpath.write_text("hello world", encoding="utf-8")
        mod = self.compile("""
        from posix import open, read, close, O_RDONLY

        def read_file(path: str, n: i32) -> str:
            fd: i32 = open(path, O_RDONLY)
            result: str = read(fd, n)
            close(fd)
            return result
        """)
        assert mod.read_file(str(fpath), 11) == "hello world"
        # Requesting fewer bytes than available
        assert mod.read_file(str(fpath), 5) == "hello"

    @skip_backends("C", reason="WASI sandbox cannot access host filesystem paths")
    def test_open_write(self, tmp_path):
        fpath = tmp_path / "out.txt"
        mod = self.compile("""
        from posix import open, write, close, O_WRONLY, O_CREAT, O_TRUNC

        def write_file(path: str, data: str) -> i32:
            fd: i32 = open(path, O_WRONLY | O_CREAT | O_TRUNC)
            n: i32 = write(fd, data)
            close(fd)
            return n
        """)
        n = mod.write_file(str(fpath), "spy rocks")
        assert n == 9
        assert fpath.read_text(encoding="utf-8") == "spy rocks"

    def test_o_flags_constants(self):
        mod = self.compile("""
        from posix import O_RDONLY, O_WRONLY, O_RDWR, O_CREAT, O_TRUNC, O_APPEND, O_EXCL

        def get_rdonly() -> i32: return O_RDONLY
        def get_wronly() -> i32: return O_WRONLY
        def get_rdwr()   -> i32: return O_RDWR
        def get_creat()  -> i32: return O_CREAT
        def get_trunc()  -> i32: return O_TRUNC
        def get_append() -> i32: return O_APPEND
        def get_excl()   -> i32: return O_EXCL
        """)
        assert mod.get_rdonly() == os.O_RDONLY
        assert mod.get_wronly() == os.O_WRONLY
        assert mod.get_rdwr() == os.O_RDWR
        assert mod.get_creat() == os.O_CREAT
        assert mod.get_trunc() == os.O_TRUNC
        assert mod.get_append() == os.O_APPEND
        assert mod.get_excl() == os.O_EXCL

    def test_open_nonexistent(self, tmp_path):
        mod = self.compile("""
        from posix import open, O_RDONLY

        def foo(path: str) -> i32:
            return open(path, O_RDONLY)
        """)
        with SPyError.raises("W_OSError", match="No such file or directory"):
            mod.foo(str(tmp_path / "nonexistent.txt"))

    def test_read_invalid_fd(self):
        mod = self.compile("""
        from posix import read

        def foo() -> str:
            return read(-1, 64)
        """)
        with SPyError.raises("W_OSError", match="Bad file descriptor"):
            mod.foo()

    def test_write_invalid_fd(self):
        mod = self.compile("""
        from posix import write

        def foo() -> i32:
            return write(-1, "data")
        """)
        with SPyError.raises("W_OSError", match="Bad file descriptor"):
            mod.foo()

    def test_close_invalid_fd(self):
        mod = self.compile("""
        from posix import close

        def foo() -> None:
            close(-1)
        """)
        with SPyError.raises("W_OSError", match="Bad file descriptor"):
            mod.foo()
