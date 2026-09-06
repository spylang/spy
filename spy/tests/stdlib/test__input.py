import io
import subprocess

from spy.errors import SPyError
from spy.tests.support import (
    CompilerTest,
    expect_errors,
    only_native,
    skip_backends,
)


class TestInput(CompilerTest):
    @skip_backends("C", reason="stdin not injectable in the C backend")
    def test_input_prompt(self, monkeypatch, capfd):
        monkeypatch.setattr("sys.stdin", io.StringIO("Alice\n"))
        src = """
        def foo(prompt: str) -> str:
            return input(prompt)
        """
        mod = self.compile(src)
        assert mod.foo("Enter your name: ") == "Alice"
        out, err = capfd.readouterr()
        assert out == "Enter your name: "

    @skip_backends("C", reason="stdin not injectable in the C backend")
    def test_input_no_prompt(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO("Alice\n"))
        src = """
        def foo() -> str:
            return input()
        """
        mod = self.compile(src)
        assert mod.foo() == "Alice"

    @skip_backends("C", reason="stdin not injectable in the C backend")
    def test_input_strips_newline(self, monkeypatch):
        # input() strips the trailing newline, like CPython
        monkeypatch.setattr("sys.stdin", io.StringIO("Alice\n"))
        src = """
        def foo() -> str:
            return input("> ")
        """
        mod = self.compile(src)
        assert mod.foo() == "Alice"

    @skip_backends("C", reason="stdin not injectable in the C backend")
    def test_input_multiple_lines(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO("first\nsecond\n"))
        src = """
        def foo() -> str:
            a = input()
            b = input()
            return a + "|" + b
        """
        mod = self.compile(src)
        assert mod.foo() == "first|second"

    @skip_backends("C", reason="stdin not injectable in the C backend")
    def test_input_eof(self, monkeypatch):
        # at EOF, input() raises EOFError, like CPython
        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        src = """
        def foo() -> str:
            return input()
        """
        mod = self.compile(src)
        with SPyError.raises("W_EOFError", match="EOF when reading a line"):
            mod.foo()

    @skip_backends("C", reason="stdin not injectable in the C backend")
    def test_input_wrong_type(self):
        src = """
        def foo() -> str:
            return input(42)
        """
        errors = expect_errors(
            "input() argument must be str, not `i32`",
            ("this is `i32`", "42"),
        )
        self.compile_raises(src, "foo", errors)

    @skip_backends("C", reason="stdin not injectable in the C backend")
    def test_input_too_many_args(self):
        src = """
        def foo() -> str:
            return input("a", "b")
        """
        errors = expect_errors(
            "input expected at most 1 argument, got 2",
            ("this is the extra argument", '"b"'),
        )
        self.compile_raises(src, "foo", errors)


@only_native
class TestInputNative(CompilerTest):
    def test_input_native(self):
        src = """
        def main() -> None:
            name = input("Enter your name: ")
            print(name)
        """
        exe = self.compile(src)
        out = subprocess.check_output([str(exe.f)], input=b"Alice\n")
        assert out == b"Enter your name: Alice\n"
