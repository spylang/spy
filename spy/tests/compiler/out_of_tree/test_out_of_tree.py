import re
import subprocess

import py
import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest, only_interp, skip_backends
from spy.vm.vm import SPyVM

MYMOD_PATH = py.path.local(__file__).dirpath("mymod")


@pytest.fixture(scope="module", autouse=True)
def build_mymod():
    archive = MYMOD_PATH.join("build", "wasi", "debug", "libmymod.a")
    sources = MYMOD_PATH.listdir("*.c") + MYMOD_PATH.listdir("*.h")
    if archive.exists() and all(archive.mtime() >= src.mtime() for src in sources):
        return
    subprocess.run(
        ["make", "TARGET=wasi"],
        cwd=str(MYMOD_PATH),
        check=True,
    )


class TestOutOfTree(CompilerTest):
    def test_simple(self):
        # override self.vm with our custom SPyVM
        self.vm = SPyVM(extra_vm_modules=[str(MYMOD_PATH)])
        self.vm.path.append(str(self.tmpdir))
        #
        mod = self.compile("""
        from mymod import get_name

        def foo() -> str:
            return get_name()
        """)
        assert mod.foo() == "hello from mymod"

    def test_c_callback(self):
        self.vm = SPyVM(extra_vm_modules=[str(MYMOD_PATH)])
        self.vm.path.append(str(self.tmpdir))
        mod = self.compile("""
        from unsafe import c_callback, c_func_ptr
        from mymod import run_callback

        @c_callback
        def double(x: i32) -> i32:
            return x * 2

        def run() -> i32:
            return run_callback(double, 21)
        """)
        assert mod.run() == 42

    def test_c_callback_blue_factory(self):
        # A @blue function generates a specialised red callback per compile-time
        # constant; each becomes a distinct C symbol that C can call back through.
        self.vm = SPyVM(extra_vm_modules=[str(MYMOD_PATH)])
        self.vm.path.append(str(self.tmpdir))
        mod = self.compile("""
        from unsafe import c_callback, c_func_ptr
        from mymod import run_callback

        CB = c_func_ptr[i32, i32]

        @blue
        def make_adder(n: i32) -> CB:
            @c_callback
            def adder(x: i32) -> i32:
                return x + n
            return adder

        add5 = make_adder(5)
        add10 = make_adder(10)

        def run() -> i32:
            return run_callback(add5, 1) + run_callback(add10, 1)
        """)
        assert mod.run() == 17  # (1+5) + (1+10)
