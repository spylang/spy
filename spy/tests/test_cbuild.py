from subprocess import getstatusoutput
import pytest
from spy.llwasm import LLWasmInstance
from spy.cbuild import get_toolchain
from spy.tests.support import CTest

class TestToolchain(CTest):

    @pytest.mark.parametrize("toolchain", ["zig", "clang"])
    def test_c2wasm(self, toolchain):
        self.toolchain = get_toolchain(toolchain)
        src = r"""
        int add(int x, int y) {
            return x+y;
        }
        """
        test_wasm = self.compile(src, exports=['add'])
        ll = LLWasmInstance.from_file(test_wasm)
        assert ll.call('add', 4, 8) == 12

    @pytest.mark.parametrize("toolchain", ["native", "emscripten"])
    def test_c2exe(self, toolchain):
        self.toolchain = get_toolchain(toolchain)
        src = r"""
        #include <stdio.h>
        #include "spy.h"
        int main(void) {
            printf("hello world\n");
            spy_debug_log("hello debug");
        }
        """
        test_exe = self.compile_exe(src)
        if toolchain == 'native':
            status, out = getstatusoutput(str(test_exe))
        elif toolchain == 'emscripten':
            status, out = getstatusoutput(f"node {test_exe}")
        assert status == 0
        assert out == 'hello world\nhello debug'
