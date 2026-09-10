import subprocess

from spy.errors import SPyError
from spy.tests.support import (
    CompilerTest,
    expect_errors,
    only_native,
)


class TestInput(CompilerTest):
    def test_input_prompt(self, capfd):
        self.set_wasi_stdin("Alice\n")
        src = """
        def foo(prompt: str) -> str:
            return input(prompt)
        """
        mod = self.compile(src)
        assert mod.foo("Enter your name: ") == "Alice"
        out, err = capfd.readouterr()
        assert out == "Enter your name: "

    def test_input_no_prompt(self):
        self.set_wasi_stdin("Alice\n")
        src = """
        def foo() -> str:
            return input()
        """
        mod = self.compile(src)
        assert mod.foo() == "Alice"

    def test_input_strips_newline(self):
        # input() strips the trailing newline, like CPython
        self.set_wasi_stdin("Alice\n")
        src = """
        def foo() -> str:
            return input("> ")
        """
        mod = self.compile(src)
        assert mod.foo() == "Alice"

    def test_input_strips_crlf(self):
        # input() also strips a trailing \r, to handle CRLF line endings
        self.set_wasi_stdin("Alice\r\n")
        src = """
        def foo() -> str:
            return input()
        """
        mod = self.compile(src)
        assert mod.foo() == "Alice"

    def test_input_multiple_lines(self):
        self.set_wasi_stdin("first\nsecond\n")
        src = """
        def foo() -> str:
            a = input()
            b = input()
            return a + "|" + b
        """
        mod = self.compile(src)
        assert mod.foo() == "first|second"

    def test_input_eof(self):
        # at EOF, input() raises EOFError, like CPython
        self.set_wasi_stdin("")
        src = """
        def foo() -> str:
            return input()
        """
        mod = self.compile(src)
        with SPyError.raises("W_EOFError", match="EOF when reading a line"):
            mod.foo()

    def test_input_wrong_type(self):
        src = """
        def foo() -> str:
            return input(42)
        """
        errors = expect_errors(
            "mismatched types",
            ("expected `str`, got `i32`", "42"),
        )
        self.compile_raises(src, "foo", errors)

    def test_input_too_many_args(self):
        src = """
        def foo() -> str:
            return input("a", "b")
        """
        errors = expect_errors(
            "this function takes from 0 to 1 arguments but 2 arguments were supplied",
            ("1 extra argument", '"b"'),
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
