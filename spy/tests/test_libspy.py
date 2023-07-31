import struct
import pytest
from spy.pywasm import LLWasmInstance
from spy.tests.support import CTest

def mk_spy_Str(utf8: bytes) -> bytes:
    """
    Return the spy_Str representation of the given utf8 bytes.

    For example, for b'hello' we have the following in-memory repr:
         <i   4 bytes of length, little endian
         5s   5 bytes of data (b'hello')
    """
    n = len(utf8)
    fmt = f'<i{n}s'
    return struct.pack(fmt, n, utf8)

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
        abc = llmod.mem.read(p1, 4)
        assert abc == b'ABC\0'
        xyz = llmod.mem.read(p2, 4)
        assert xyz == b'XYZ\0'

    def test_str(self):
        src = r"""
        #include <spy.h>

        spy_Str H = {6, "hello "};

        spy_Str *mk_W(void) {
            spy_Str *s = spy_StrAlloc(5);
            memcpy((void*)s->utf8, "world", 5);
            return s;
        }
        """
        test_wasm = self.compile(src, exports=['H', 'mk_W'])
        llmod = LLWasmInstance.from_file(test_wasm)
        ptr_H = llmod.read_global('H')
        assert llmod.mem.read(ptr_H, 10) == mk_spy_Str(b'hello ')
        #
        ptr_W = llmod.call('mk_W')
        assert llmod.mem.read(ptr_W, 9) == mk_spy_Str(b'world')
        #
        ptr_HW = llmod.call('spy_StrAdd', ptr_H, ptr_W)
        assert llmod.mem.read(ptr_HW, 15) == mk_spy_Str(b'hello world')
