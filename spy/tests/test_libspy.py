import pytest
from spy.pywasm import LLWasmInstance
from spy.tests.support import CTest

class TestLibSPy(CTest):

    def test_walloc(self):
        src = r"""
        #include <spy.h>

        char *
        WASM_EXPORT(make_str)(char a, char b, char c) {
            char *buf = malloc(4);
            buf[0] = a;
            buf[1] = b;
            buf[2] = c;
            buf[3] = '\0';
            return buf;
        }
        """
        test_wasm = self.compile(src)
        llmod = LLWasmInstance.from_file(test_wasm)
        p1 = llmod.call('make_str', ord('A'), ord('B'), ord('C'))
        p2 = llmod.call('make_str', ord('X'), ord('Y'), ord('Z'))
        assert p1 != p2
        abc = llmod.read_mem(p1, 4)
        assert abc == b'ABC\0'
        xyz = llmod.read_mem(p2, 4)
        assert xyz == b'XYZ\0'
