import pytest
from spy.llwasm import LLWasmModule, LLWasmInstance
from spy.tests.support import CTest

class TestLLWasm(CTest):

    def test_call(self):
        src = r"""
        int add(int x, int y) {
            return x+y;
        }
        """
        test_wasm = self.compile(src, exports=['add'])
        llmod = LLWasmInstance.from_file(test_wasm)
        assert llmod.call('add', 4, 8) == 12

    def test_all_exports(self):
        src = r"""
        int add(int x, int y) {
            return x+y;
        }
        int x;
        int y;
        """
        test_wasm = self.compile(src, exports=['add', 'x', 'y'])
        llmod = LLWasmInstance.from_file(test_wasm)
        assert llmod.all_exports() == ['memory', 'add', 'x', 'y']

    def test_read_global(self):
        src = r"""
        #include <stdint.h>
        int32_t x = 100;
        int16_t y = 200;
        int16_t z = 300;
        """
        test_wasm = self.compile(src, exports=['x', 'y', 'z'])
        llmod = LLWasmInstance.from_file(test_wasm)
        assert llmod.read_global('x', 'int32_t') == 100
        assert llmod.read_global('y', 'int16_t') == 200
        assert llmod.read_global('z', 'int16_t') == 300

    def test_read_mem(self):
        src = r"""
        #include <stdint.h>
        const char *hello = "hello";
        int32_t foo[] = {100, 200};
        """
        test_wasm = self.compile(src, exports=['hello', 'foo'])
        llmod = LLWasmInstance.from_file(test_wasm)
        ptr = llmod.read_global('hello', 'void *')
        assert llmod.mem.read(ptr, 6) == b'hello\0'
        #
        ptr = llmod.read_global('foo')
        assert llmod.mem.read_i32(ptr) == 100
        assert llmod.mem.read_i32(ptr+4) == 200

    def test_write_mem(self):
        src = r"""
        #include <stdint.h>
        int8_t foo[] = {10, 20, 30};
        int32_t foo_total(void) {
            return foo[0] + foo[1] + foo[2];
        }
        """
        test_wasm = self.compile(src, exports=['foo', 'foo_total'])
        llmod = LLWasmInstance.from_file(test_wasm)
        assert llmod.call('foo_total') == 60
        #
        ptr = llmod.read_global('foo')
        llmod.mem.write(ptr, bytearray([40, 50, 60]))
        assert llmod.call('foo_total') == 150

    def test_multiple_instances(self):
        src = r"""
        int x = 100;
        int inc(void) {
            return ++x;
        }
        """
        test_wasm = self.compile(src, exports=['inc'])
        llmod_factory = LLWasmModule(test_wasm)
        llmod1 = llmod_factory.instantiate()
        llmod2 = llmod_factory.instantiate()
        assert llmod1.call('inc') == 101
        assert llmod1.call('inc') == 102
        assert llmod1.call('inc') == 103
        #
        assert llmod2.call('inc') == 101
        assert llmod2.call('inc') == 102
        assert llmod2.call('inc') == 103
