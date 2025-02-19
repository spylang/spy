import pytest
from spy.llwasm import LLWasmModule, LLWasmInstance, HostModule
from spy.tests.support import CTest
from pytest_pyodide import run_in_pyodide

class TestLLWasm(CTest):

    def test_call(self, selenium):
        src = r"""
        int add(int x, int y) {
            return x+y;
        }
        """
        test_wasm = self.compile(src, exports=['add'])
        @run_in_pyodide
        def fn(selenium, test_wasm):
            from spy.llwasm_pyodide import LLWasmInstance
            
            ll = LLWasmInstance.from_file(test_wasm)
            assert ll.call('add', 4, 8) == 12

        fn(selenium, test_wasm)

    def test_all_exports(self, selenium):
        src = r"""
        int add(int x, int y) {
            return x+y;
        }
        int x;
        int y;
        """
        test_wasm = self.compile(src, exports=['add', 'x', 'y'])
        
        @run_in_pyodide
        def fn(selenium, test_wasm):
            from spy.llwasm_pyodide import LLWasmInstance

            ll = LLWasmInstance.from_file(test_wasm)
            exports = ll.all_exports()
            exports.sort()
            assert exports == ['_initialize', 'add', 'memory', 'x', 'y']
        
        fn(selenium, test_wasm)

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
        #
        ll.mem.write_i8(ptr, 100)
        assert ll.call('foo_total') == 210

    def test_multiple_instances(self):
        src = r"""
        int x = 100;
        int inc(void) {
            return ++x;
        }
        """
        test_wasm = self.compile(src, exports=['inc'])
        llmod = LLWasmModule(test_wasm)
        ll1 = LLWasmInstance(llmod)
        ll2 = LLWasmInstance(llmod)
        assert ll1.call('inc') == 101
        assert ll1.call('inc') == 102
        assert ll1.call('inc') == 103
        #
        assert ll2.call('inc') == 101
        assert ll2.call('inc') == 102
        assert ll2.call('inc') == 103

    def test_HostModule(self):
        src = r"""
        #include <stdint.h>
        #include "spy.h"

        int32_t WASM_IMPORT(add)(int32_t x, int32_t y);
        int32_t WASM_IMPORT(square)(int32_t x);
        void WASM_IMPORT(record)(int32_t x);

        int32_t compute(void) {
            record(100);
            record(200);
            return square(add(10, 20));
        }
        """
        test_wasm = self.compile(src, exports=['compute'])
        llmod = LLWasmModule(test_wasm)

        class Math(HostModule):
            def env_add(self, x: int, y: int) -> int:
                return x + y

            def env_square(self, x: int) -> int:
                return x * x

        class Recorder(HostModule):
            log: list[int]

            def __init__(self, *args, **kwargs) -> None:
                self.log = []

            def env_record(self, x: int) -> None:
                self.log.append(x)

        math = Math()
        recorder = Recorder()
        ll = LLWasmInstance(llmod, [math, recorder])
        assert ll.call('compute') == 900
        assert recorder.log == [100, 200]
