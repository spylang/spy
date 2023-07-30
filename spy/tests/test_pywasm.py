import pytest
from spy.pywasm import LLWasmModule, LLWasmInstance
from spy.tests.support import CTest

class TestPyWasm(CTest):

    def test_call(self):
        src = r"""
        #include "spy.h"

        int
        WASM_EXPORT(add)(int x, int y) {
            return x+y;
        }
        """
        test_wasm = self.compile(src)
        llmod = LLWasmInstance.from_file(test_wasm)
        assert llmod.call('add', 4, 8) == 12

    def test_read_mem(self):
        src = r"""
        #include "spy.h"

        const char *
        WASM_EXPORT(get_hello)(void) {
            return "hello";
        }

        int32_t foo[] = {100, 200};
        int32_t *
        WASM_EXPORT(get_foo)(void) {
            return foo;
        }
        """
        test_wasm = self.compile(src)
        llmod = LLWasmInstance.from_file(test_wasm)
        ptr = llmod.call('get_hello')
        assert llmod.read_mem(ptr, 6) == b'hello\0'
        #
        ptr = llmod.call('get_foo')
        assert llmod.read_mem_i32(ptr) == 100
        assert llmod.read_mem_i32(ptr+4) == 200

    def test_write_mem(self):
        src = r"""
        #include "spy.h"

        char foo[] = {'f', 'o', 'o', '\0'};
        char *
        WASM_EXPORT(get_foo)(void) {
            return foo;
        }
        """
        test_wasm = self.compile(src)
        llmod = LLWasmInstance.from_file(test_wasm)
        ptr = llmod.call('get_foo')
        assert llmod.read_mem(ptr, 4) == b'foo\0'
        llmod.write_mem(ptr, b'bar\0')
        assert llmod.read_mem(ptr, 4) == b'bar\0'

    def test_multiple_instances(self):
        src = r"""
        #include "spy.h"

        int x = 100;
        int WASM_EXPORT(inc)(void) {
            return ++x;
        }
        """
        test_wasm = self.compile(src)
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
