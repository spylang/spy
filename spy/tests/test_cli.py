import json
import re
import subprocess
import sys
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
        "\x1b[48;5;174m": "[R]",  # 256-color: light pink (red)
        "\x1b[48;5;110m": "[B]",  # 256-color: light steel blue (blue)
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

    def write(self, filename: str, src: str) -> Any:
        src = textwrap.dedent(src)
        srcfile = self.tmpdir.join(filename)
        srcfile.write(src)
        return srcfile

    @pytest.fixture
    def init(self, tmpdir):
        self.tmpdir = tmpdir
        self.runner = CliRunner()
        src = """
        def main() -> None:
            print("hello world")
        """
        self.main_spy = self.write("main.spy", src)

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
        _, stdout = self.run("pyparse", self.main_spy)
        assert stdout.startswith("py:Module(")

    def test_parse(self):
        _, stdout = self.run("parse", self.main_spy)
        assert stdout.startswith("Module(")

    def test_execute(self):
        argsets = [["execute"], []]  # No subcommand is equivalent to execute command
        for argset in argsets:
            _, stdout = self.run(*argset, self.main_spy)
            assert stdout == "hello world\n"

    def test_timeit(self):
        _, stdout = self.run("--timeit", self.main_spy)
        assert "main()" in stdout

    def test_redshift_and_run(self):
        _, stdout = self.run("redshift", "-x", self.main_spy)
        assert stdout == "hello world\n"

    def test_redshift_dump_ast(self):
        _, stdout = self.run("redshift", "--format", "ast", self.main_spy)
        assert stdout.startswith("`main::main` = FuncDef(")

    def test_redshift_full_fqn(self):
        _, stdout = self.run("redshift", "--full-fqn", self.main_spy)
        assert "builtins::print_str" in stdout

    def test_redshift_spy_output(self):
        _, stdout = self.run("redshift", self.main_spy)
        assert stdout.startswith("def main() -> None:")

    def test_colorize_ast(self):
        _, stdout = self.run("colorize", "--format", "ast", self.main_spy)
        assert stdout.startswith("Module(")

    def test_colorize_json(self):
        _, stdout = self.run("colorize", "--format", "json", self.main_spy)
        content = json.loads(stdout)
        keys = "line", "col", "length", "type"
        assert all(key in obj for key in keys for obj in content)

    def test_colorize_source(self):
        # source formatting is the default - run all the examples below
        # with both 'colorize --format spy' and bare 'colorize'
        src = """
        def factorial(n: i32) -> i32:
            res = 1
            for i in range(n):
                res *= (i+1)
            return res

        def main() -> None:
            print(factorial(5))
        """
        test1_spy = self.write("test1.spy", src)
        _, stdout = self.run("colorize", test1_spy, decolorize_stdout=False)
        # B stands for Blue, R for Red, [/COLOR] means that the ANSI has been reset
        expected = textwrap.dedent("""
        def factorial(n: i32) -> i32:
            [R]res = [/COLOR][B]1[/COLOR]
            for i in [B]range[/COLOR][R](n)[/COLOR]:
                res *= ([R]i+[/COLOR][B]1[/COLOR])
            return [R]res[/COLOR]

        def main() -> None:
            [B]print[/COLOR][R]([/COLOR][B]factorial[/COLOR][R]([/COLOR][B]5[/COLOR][R]))[/COLOR]
        """)  # noqa
        assert ansi_to_readable(stdout.strip()) == expected.strip()

        src = """
        @blue
        def get_Type():
            return int

        def main() -> None:
            T = get_Type()    # T is blue
            print(T)
        """
        test2_spy = self.write("test2.spy", src)
        _, stdout = self.run("colorize", test2_spy, decolorize_stdout=False)
        expected = textwrap.dedent("""
        @blue
        def get_Type():
            return int

        def main() -> None:
            [B]T = get_Type()[/COLOR]    # T is blue
            [B]print[/COLOR][R]([/COLOR][B]T[/COLOR][R])[/COLOR]
        """)  # noqa
        assert ansi_to_readable(stdout.strip()) == expected.strip()

    def test_cwrite(self):
        self.run("build", "--no-compile", "--build-dir", self.tmpdir, self.main_spy)
        main_c = self.tmpdir.join("src", "main.c")
        assert main_c.exists()
        csrc = main_c.read()
        assert csrc.startswith('#include "main.h"')

    @pytest.mark.parametrize(
        "target",
        [
            pytest.param("native"),
            pytest.param(
                "native-static",
                marks=pytest.mark.skipif(
                    sys.platform == "darwin",
                    reason="not supported on macOS",
                ),
            ),
            pytest.param("wasi"),
            pytest.param("emscripten", marks=pytest.mark.emscripten),
        ],
    )
    def test_build(self, target):
        build_args = ["build", "--build-dir", self.tmpdir]
        if target == "native-static":
            build_args += ["--target", "native", "--static"]
        else:
            build_args += ["--target", target]
        build_args.append(self.main_spy)
        res, stdout = self.run(*build_args)
        if target in ("native", "native-static"):
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

    def test_build_and_execute(self, capfd):
        res, stdout = self.run(
            "build",
            "-x",
            "--target", "native",
            "--build-dir", self.tmpdir,
            self.main_spy,
        )  # fmt: skip
        # hack hack hack since the stdout of the subprocess isn't captured
        # by the test runner, check the output from timeit instead
        out, err = capfd.readouterr()
        assert "hello world" in out

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

    def test_cleanup_without_directory(self, monkeypatch):
        # Create fake .spyc files in __pycache__
        pycache = self.tmpdir.join("__pycache__")
        pycache.mkdir()
        spyc1 = pycache.join("mod1.spyc")
        spyc2 = pycache.join("mod2.spyc")
        spyc1.write("")
        spyc2.write("")

        # Run cleanup from tmpdir (without filename, uses cwd)
        monkeypatch.chdir(self.tmpdir)
        res, stdout = self.run("cleanup")
        assert not spyc1.exists()
        assert not spyc2.exists()
        assert "2 file(s) removed" in stdout

    def test_cleanup_with_directory(self):
        # Create fake .spyc files in __pycache__
        pycache = self.tmpdir.join("__pycache__")
        pycache.mkdir()
        spyc1 = pycache.join("main.spyc")
        spyc1.write("")

        # NOTE: this might remove stdlib .spyc files, we don't know the precise number
        res, stdout = self.run("cleanup", pycache)
        assert not spyc1.exists()
        assert "1 file(s) removed" in stdout

    def test_cleanup_no_files(self):
        # Run cleanup when no .spyc files exist
        res, stdout = self.run("cleanup", self.tmpdir)

        # When run with no folder, cleanup tidies up the standardlib folder as well, which may have spyc files in it
        assert "No .spyc files found" in stdout or (
            "Removed" in stdout and ".spyc file(s)" in stdout
        )

    def test_symtable(self):
        _, stdout = self.run("symtable", self.main_spy)
        assert "<SymTable 'main::main'" in stdout

    def test_imports(self):
        _, stdout = self.run("imports", self.main_spy)
        assert stdout.startswith("Import tree:")

    def test_interp_exit_code(self):
        src = """
        def main() -> i32:
            return 99
        """
        f = self.write("test.spy", src)
        res = self.runner.invoke(app, [str(f)])
        assert res.exit_code == 99

    def test_compile_exit_code(self):
        src = """
        def main() -> i32:
            return 99
        """
        f = self.write("test.spy", src)
        self.run("build", f)
        test_exe = self.tmpdir.join("build", "test")
        status, out = getstatusoutput([str(test_exe)])
        assert status == 99

    def test_interp_argv(self):
        src = """
        def main(argv: list[str]) -> None:
            for a in argv:
                print(a)
        """
        f = self.write("test.spy", src)
        res = self.runner.invoke(app, [str(f), "aaa", "bbb", "ccc"])
        assert res.exit_code == 0
        output = decolorize(res.output)
        assert output.split() == [str(f), "aaa", "bbb", "ccc"]

    def test_compile_argv(self):
        src = """
        def main(argv: list[str]) -> None:
            for a in argv:
                print(a)
        """
        f = self.write("test.spy", src)
        self.run("build", f)
        test_exe = self.tmpdir.join("build", "test")
        status, out = getstatusoutput(f"{test_exe} aaa bbb ccc")
        assert out.split() == [str(test_exe), "aaa", "bbb", "ccc"]

    def test_redshift_argv(self):
        src = """
        def main(argv: list[str]) -> None:
            for a in argv:
                print(a)
        """
        f = self.write("test.spy", src)
        res = self.runner.invoke(app, ["redshift", "-x", str(f), "aaa", "bbb", "ccc"])
        assert res.exit_code == 0
        output = decolorize(res.output)
        assert output.split() == [str(f), "aaa", "bbb", "ccc"]
