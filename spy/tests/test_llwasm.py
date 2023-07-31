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
        ll = LLWasmInstance.from_file(test_wasm)
        assert ll.call('add', 4, 8) == 12

    def test_all_exports(self):
        src = r"""
        int add(int x, int y) {
            return x+y;
        }
        int x;
        int y;
        """
        test_wasm = self.compile(src, exports=['add', 'x', 'y'])
        ll = LLWasmInstance.from_file(test_wasm)
        assert ll.all_exports() == ['memory', 'add', 'x', 'y']

    def test_read_global(self):
        src = r"""
        #include <stdint.h>
        int32_t x = 100;
        int16_t y = 200;
        int16_t z = 300;
        """
        test_wasm = self.compile(src, exports=['x', 'y', 'z'])
        ll = LLWasmInstance.from_file(test_wasm)
        assert ll.read_global('x', 'int32_t') == 100
        assert ll.read_global('y', 'int16_t') == 200
        assert ll.read_global('z', 'int16_t') == 300

    def test_read_mem(self):
        src = r"""
        #include <stdint.h>
        const char *hello = "hello";
        int32_t foo[] = {100, 200};
        """
        test_wasm = self.compile(src, exports=['hello', 'foo'])
        ll = LLWasmInstance.from_file(test_wasm)
        ptr = ll.read_global('hello', 'void *')
        assert ll.mem.read(ptr, 6) == b'hello\0'
        #
        ptr = ll.read_global('foo')
        assert ll.mem.read_i32(ptr) == 100
        assert ll.mem.read_i32(ptr+4) == 200

    def test_write_mem(self):
        src = r"""
        #include <stdint.h>
        int8_t foo[] = {10, 20, 30};
        int32_t foo_total(void) {
            return foo[0] + foo[1] + foo[2];
        }
        """
        test_wasm = self.compile(src, exports=['foo', 'foo_total'])
        ll = LLWasmInstance.from_file(test_wasm)
        assert ll.call('foo_total') == 60
        #
        ptr = ll.read_global('foo')
        ll.mem.write(ptr, bytearray([40, 50, 60]))
        assert ll.call('foo_total') == 150

    def test_multiple_instances(self):
        src = r"""
        int x = 100;
        int inc(void) {
            return ++x;
        }
        """
        test_wasm = self.compile(src, exports=['inc'])
        ll_factory = LLWasmModule(test_wasm)
        ll1 = ll_factory.instantiate()
        ll2 = ll_factory.instantiate()
        assert ll1.call('inc') == 101
        assert ll1.call('inc') == 102
        assert ll1.call('inc') == 103
        #
        assert ll2.call('inc') == 101
        assert ll2.call('inc') == 102
        assert ll2.call('inc') == 103
