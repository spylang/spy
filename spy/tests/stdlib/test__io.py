from spy.errors import SPyError
from spy.tests.support import CompilerTest, skip_backends


@skip_backends("C", reason="WASI sandbox cannot access host filesystem paths")
class TestIO(CompilerTest):
    def test_read(self, tmp_path):
        fpath = tmp_path / "hello.txt"
        fpath.write_text("hello world", encoding="utf-8")
        mod = self.compile("""
        from _io import FileIO

        def read_file(path: str, n: i32) -> str:
            f = FileIO(path, "r")
            result: str = f.read(n)
            f.close()
            return result
        """)
        assert mod.read_file(str(fpath), 11) == "hello world"
        assert mod.read_file(str(fpath), 5) == "hello"

    def test_write(self, tmp_path):
        fpath = tmp_path / "out.txt"
        mod = self.compile("""
        from _io import FileIO

        def write_file(path: str, data: str) -> i32:
            f = FileIO(path, "w")
            n: i32 = f.write(data)
            f.close()
            return n
        """)
        n = mod.write_file(str(fpath), "spy rocks")
        assert n == 9
        assert fpath.read_text(encoding="utf-8") == "spy rocks"

    def test_write_truncates(self, tmp_path):
        fpath = tmp_path / "out.txt"
        fpath.write_text("old content here", encoding="utf-8")
        mod = self.compile("""
        from _io import FileIO

        def write_file(path: str, data: str) -> None:
            f = FileIO(path, "w")
            f.write(data)
            f.close()
        """)
        mod.write_file(str(fpath), "new")
        assert fpath.read_text(encoding="utf-8") == "new"

    def test_append(self, tmp_path):
        fpath = tmp_path / "out.txt"
        fpath.write_text("hello ", encoding="utf-8")
        mod = self.compile("""
        from _io import FileIO

        def append_file(path: str, data: str) -> None:
            f = FileIO(path, "a")
            f.write(data)
            f.close()
        """)
        mod.append_file(str(fpath), "world")
        assert fpath.read_text(encoding="utf-8") == "hello world"

    def test_open_nonexistent(self, tmp_path):
        mod = self.compile("""
        from _io import FileIO

        def open_file(path: str) -> FileIO:
            return FileIO(path, "r")
        """)
        with SPyError.raises("W_OSError", match="No such file or directory"):
            mod.open_file(str(tmp_path / "nonexistent.txt"))

    def test_invalid_mode(self, tmp_path):
        fpath = tmp_path / "f.txt"
        fpath.write_text("x", encoding="utf-8")
        mod = self.compile("""
        from _io import FileIO

        def open_file(path: str) -> FileIO:
            return FileIO(path, "x")
        """)
        with SPyError.raises("W_ValueError", match="invalid mode"):
            mod.open_file(str(fpath))
