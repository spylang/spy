import re
import subprocess
import textwrap
from subprocess import getstatusoutput
from typing import Any

import pytest
from typer.testing import CliRunner

import spy
from spy.cli import app

PYODIDE_EXE = spy.ROOT.dirpath().join("pyodide", "venv", "bin", "python")
if not PYODIDE_EXE.exists():
    PYODIDE_EXE = None  # type: ignore

# https://stackoverflow.com/a/14693789
# 7-bit C1 ANSI sequences
ANSI_ESCAPE = re.compile(
    r"""
    \x1B  # ESC
    (?:   # 7-bit C1 Fe (except CSI)
        [@-Z\\-_]
    |     # or [ for CSI, followed by a control sequence
        \[
        [0-?]*  # Parameter bytes
        [ -/]*  # Intermediate bytes
        [@-~]   # Final byte
    )
""",
    re.VERBOSE,
)


def ansi_to_readable(s: str) -> str:
    mapping = {
        "\x1b[41m": "[R]",  # red background
        "\x1b[44m": "[B]",  # blue background
        "\x1b[0m": "[/COLOR]",  # reset (end of color)
    }

    def repl(match):
        code = match.group(0)
        return mapping.get(code, "")

    return ANSI_ESCAPE.sub(repl, s)


def decolorize(s: str) -> str:
    return ANSI_ESCAPE.sub("", s)


@pytest.mark.usefixtures("init")
class TestMain:
    tmpdir: Any

    @pytest.fixture
    def init(self, tmpdir):
        self.tmpdir = tmpdir
        self.runner = CliRunner()
        self.main_spy = tmpdir.join("main.spy")
        self.factorial_spy = tmpdir.join("fatcorial.spy")
        self.blu_var_in_red_func_spy = tmpdir.join("blu_var_in_red_func.spy")
        main_src = """
        def main() -> None:
            print("hello world")
        """
        factorial_src = """
        def factorial(n: i32) -> i32:
            res = 1
            for i in range(n):
                res *= (i+1)
            return res

        def main() -> None:
            print(factorial(5))
        """
        blu_var_in_red_func_src = """
        @blue
        def get_Type():
            return int

        def main() -> None:
            T = get_Type()    # T is blue
            print(T)
        """
        self.main_spy.write(textwrap.dedent(main_src))
        self.factorial_spy.write(textwrap.dedent(factorial_src))
        self.blu_var_in_red_func_spy.write(textwrap.dedent(blu_var_in_red_func_src))

    def run(self, *args: Any, decolorize_stdout=True) -> Any:
        args2 = [str(arg) for arg in args]
        print("run: spy %s" % " ".join(args2))
        res = self.runner.invoke(app, args2)
        print(res.stdout)
        if res.exit_code != 0:
            raise res.exception  # type: ignore
        return res, decolorize(res.stdout) if decolorize_stdout else res.stdout

    def run_external(self, python_exe, *args: Any) -> Any:
        args2 = [str(arg) for arg in args]
        cmd = [str(python_exe), "-E", "-m", "spy"] + args2
        print(f"run_external: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(self.tmpdir),
        )
        stdout, stderr = process.communicate()
        exit_code = process.returncode

        print(f"exit_code: {exit_code}")
        print(stdout)
        print(stderr)
        if exit_code != 0:
            raise Exception("run_external failed")
        return exit_code, decolorize(stdout)

    def test_py_file_error(self):
        # Create a .py file instead of .spy
        py_file = self.tmpdir.join("test.py")
        py_file.write("print('This is a Python file')")

        # Test that passing a .py file produces an error
        res = self.runner.invoke(app, [str(py_file)])
        assert res.exit_code == 1
        assert "Error:" in res.output and ".py file, not a .spy file" in res.output

    def test_pyparse(self):
        _, stdout = self.run("--pyparse", self.main_spy)
        assert stdout.startswith("py:Module(")

    def test_parse(self):
        _, stdout = self.run("--parse", self.main_spy)
        assert stdout.startswith("Module(")

    def test_execute(self):
        _, stdout = self.run(self.main_spy)
        assert stdout == "hello world\n"

    def test_redshift_dump_spy(self):
        _, stdout = self.run("--redshift", self.main_spy)
        assert stdout.startswith("\ndef main() -> None:")

    def test_redshift_dump_ast(self):
        _, stdout = self.run("--redshift", "--parse", self.main_spy)
        assert stdout.startswith("`main::main` = FuncDef(")

    def test_redshift_and_execute(self):
        _, stdout = self.run("--redshift", "--execute", self.main_spy)
        assert stdout == "hello world\n"

    def test_colorize_ast(self):
        _, stdout = self.run("--colorize", "--parse", self.main_spy)
        assert stdout.startswith("Module(")

    def test_colorize(self):
        _, stdout = self.run("--colorize", self.factorial_spy, decolorize_stdout=False)
        # B stands for Blue, R for Red, [/COLOR] means that the ANSI has been reset
        expected_outout = """\
        def factorial(n: i32) -> i32:
            [R]res = [/COLOR][B]1[/COLOR]
            for i in [B]range[/COLOR][R](n)[/COLOR]:
                res *= ([R]i+[/COLOR][B]1[/COLOR])
            return [R]res[/COLOR]

        def main() -> None:
            [B]print[/COLOR][R]([/COLOR][B]factorial[/COLOR][R]([/COLOR][B]5[/COLOR][R]))[/COLOR]"""  # noqa
        assert ansi_to_readable(stdout.strip()) == textwrap.dedent(expected_outout)
        _, stdout = self.run(
            "--colorize", self.blu_var_in_red_func_spy, decolorize_stdout=False
        )
        expected_outout = """\
        @blue
        def get_Type():
            return int

        def main() -> None:
            [B]T = get_Type()[/COLOR]    # T is blue
            [B]print[/COLOR][R]([/COLOR][B]T[/COLOR][R])[/COLOR]"""  # noqa
        assert ansi_to_readable(stdout.strip()) == textwrap.dedent(expected_outout)

    def test_cwrite(self):
        self.run("--cwrite", "--build-dir", self.tmpdir, self.main_spy)
        main_c = self.tmpdir.join("src", "main.c")
        assert main_c.exists()
        csrc = main_c.read()
        assert csrc.startswith('#include "main.h"')

    @pytest.mark.parametrize(
        "target",
        [
            pytest.param("native"),
            pytest.param("wasi"),
            pytest.param("emscripten", marks=pytest.mark.emscripten),
        ],
    )
    def test_build(self, target):
        res, stdout = self.run(
            "--compile",
            "--target", target,
            "--build-dir", self.tmpdir,
            self.main_spy,
        )  # fmt: skip
        if target == "native":
            main_exe = self.tmpdir.join("main")
            assert main_exe.exists()
            cmd = str(main_exe)
        elif target == "wasi":
            main_wasm = self.tmpdir.join("main.wasm")
            assert main_wasm.exists()
            cmd = f"python -m spy.tool.wasmtime {main_wasm}"
        else:
            main_js = self.tmpdir.join("main.mjs")
            main_wasm = self.tmpdir.join("main.wasm")
            assert main_js.exists()
            assert main_wasm.exists()
            cmd = f"node {main_js}"

        # NOTE: getstatusoutput automatically strips the trailing \n
        status, out = getstatusoutput(cmd)
        if status != 0:
            print(out)
            assert False, f"command failed: {cmd}"
        assert out == "hello world"

    @pytest.mark.skipif(PYODIDE_EXE is None, reason="./pyodide/venv not found")
    @pytest.mark.pyodide
    def test_execute_pyodide(self):
        # pyodide under node cannot access /tmp/, so we cannot try to execute
        # files which we wrote to self.tmpdir. Instead, let's try to execute
        # examples/hello.spy
        hello_spy = spy.ROOT.dirpath().join("examples", "hello.spy")
        assert hello_spy.exists()
        res, stdout = self.run_external(PYODIDE_EXE, hello_spy)
        assert stdout == "Hello world!\n"
