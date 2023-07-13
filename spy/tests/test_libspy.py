import os
import pytest
from spy.cbuild import ZigToolchain
from spy.backend.c.wrapper import LLWasmModule
from spy.tests.support import CompilerTest, no_backend

@no_backend
class TestLibSPy(CompilerTest):

    def test_walloc(self):
        src = r"""
        #include <spy.h>

        char *make_str(char a, char b, char c) {
            char *buf = malloc(4);
            buf[0] = a;
            buf[1] = b;
            buf[2] = c;
            buf[3] = '\0';
            return buf;
        }
        """
        test_c = self.write_file("test.c", src)
        test_wasm = self.builddir.join("test.wasm")
        toolchain = ZigToolchain()
        exports = ['make_str']
        toolchain.c2wasm(test_c, exports, test_wasm)
        llmod = LLWasmModule(test_wasm)
        p1 = llmod.call('make_str', ord('A'), ord('B'), ord('C'))
        p2 = llmod.call('make_str', ord('X'), ord('Y'), ord('Z'))
        assert p1 != p2
        abc = llmod.read_mem(p1, 4)
        assert abc == b'ABC\0'
        xyz = llmod.read_mem(p2, 4)
        assert xyz == b'XYZ\0'
