from typing import Any, Tuple
import re
import textwrap
import subprocess
from subprocess import getstatusoutput
import pytest
from typer.testing import CliRunner
import spy
from spy.cli import app

PYODIDE_EXE = spy.ROOT.dirpath().join('pyodide', 'venv', 'bin', 'python')
if not PYODIDE_EXE.exists():
    PYODIDE_EXE = None # type: ignore

# https://stackoverflow.com/a/14693789
# 7-bit C1 ANSI sequences
ANSI_ESCAPE = re.compile(r'''
    \x1B  # ESC
    (?:   # 7-bit C1 Fe (except CSI)
        [@-Z\\-_]
    |     # or [ for CSI, followed by a control sequence
        \[
        [0-?]*  # Parameter bytes
        [ -/]*  # Intermediate bytes
        [@-~]   # Final byte
    )
''', re.VERBOSE)

def decolorize(s: str) -> str:
    return ANSI_ESCAPE.sub('', s)


@pytest.mark.usefixtures('init')
class TestMain:
    tmpdir: Any

    @pytest.fixture
    def init(self, tmpdir):
        self.tmpdir = tmpdir
        self.runner = CliRunner()
        self.foo_spy = tmpdir.join('foo.spy')
        self.foo_spy.write(textwrap.dedent("""
        def add(x: i32, y: i32) -> i32:
            return x + y
        """))
        self.main_spy = tmpdir.join('main.spy')
        self.main_spy.write(textwrap.dedent("""
        def main() -> void:
            print("hello world")
        """))

    def run(self, *args: Any) -> Any:
        args2 = [str(arg) for arg in args]
        print('run: spy %s' % ' '.join(args2))
        res = self.runner.invoke(app, args2)
        print(res.stdout)
        if res.exit_code != 0:
            raise res.exception  # type: ignore
        return res, decolorize(res.stdout)

    def run_external(self, python_exe, *args: Any) -> Any:
        args2 = [str(arg) for arg in args]
        cmd = [str(python_exe), "-E", "-m", "spy"] + args2
        print(f'run_external: {" ".join(cmd)}')

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(self.tmpdir)
        )
        stdout, stderr = process.communicate()
        exit_code = process.returncode

        print(f"exit_code: {exit_code}")
        print(stdout)
        print(stderr)
        if exit_code != 0:
            raise Exception("run_external failed")
        return exit_code, decolorize(stdout)

    def test_pyparse(self):
        res, stdout = self.run('--pyparse', self.foo_spy)
        assert stdout.startswith('py:Module(')

    def test_parse(self):
        res, stdout = self.run('--parse', self.foo_spy)
        assert stdout.startswith('Module(')

    def test_execute(self):
        self.foo_spy.write(textwrap.dedent("""
        def main() -> void:
            print("hello world")
        """))
        res, stdout = self.run(self.foo_spy)
        assert stdout == "hello world\n"

    def test_redshift(self):
        res, stdout = self.run('--redshift', self.foo_spy)
        assert stdout.startswith('def add(x: i32, y: i32) -> i32:')

    def test_cwrite(self):
        res, stdout = self.run('--cwrite', '--build-dir', self.tmpdir, self.foo_spy)
        foo_c = self.tmpdir.join('foo.c')
        assert foo_c.exists()
        csrc = foo_c.read()
        assert csrc.startswith('#include "foo.h"')

    def test_build_wasm(self):
        res, stdout = self.run("--compile", '--build-dir', self.tmpdir, self.foo_spy)
        foo_wasm = self.tmpdir.join('foo.wasm')
        assert foo_wasm.exists()
        wasm_bytes = foo_wasm.read_binary()
        assert wasm_bytes.startswith(b'\0asm')

    @pytest.mark.parametrize("toolchain", [
        pytest.param("native"),
        pytest.param("emscripten", marks=pytest.mark.emscripten)
    ])
    def test_build(self, toolchain):
        res, stdout = self.run("--compile",
                               "--toolchain", toolchain,
                               "--build-dir", self.tmpdir,
                               self.main_spy)
        if toolchain == 'native':
            main_exe = self.tmpdir.join('main')
            assert main_exe.exists()
            cmd = str(main_exe)
        else:
            main_js = self.tmpdir.join('main.mjs')
            main_wasm = self.tmpdir.join('main.wasm')
            assert main_js.exists()
            assert main_wasm.exists()
            cmd = f'node {main_js}'

        # NOTE: getstatusoutput automatically strips the trailing \n
        status, out = getstatusoutput(cmd)
        assert status == 0
        assert out == "hello world"

    @pytest.mark.skipif(PYODIDE_EXE is None, reason='./pyodide/venv not found')
    @pytest.mark.pyodide
    def test_execute_pyodide(self):
        # pyodide under node cannot access /tmp/, so we cannot try to execute
        # files which we wrote to self.tmpdir. Instead, let's try to execute
        # examples/hello.spy
        hello_spy = spy.ROOT.dirpath().join('examples', 'hello.spy')
        assert hello_spy.exists()
        res, stdout = self.run_external(PYODIDE_EXE, hello_spy)
        assert stdout == "Hello world!\n"
