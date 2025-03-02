import pytest
from spy import ROOT
from spy.tests.support import CTest
from spy.cbuild import EmscriptenToolchain
from pytest_pyodide import run_in_pyodide

PYODIDE = ROOT.join('..', 'node_modules', 'pyodide')
HAS_PYODIDE = PYODIDE.check(exists=True)

@pytest.mark.usefixtures('init_llwasm')
class TestLLWasm(CTest):

    @pytest.fixture(params=[
        # "normal" execution, under CPython
        pytest.param('wasmtime', marks=pytest.mark.wasmtime),

        # run tests inside pyodide, using the 'emscripten' llwasm backend
        pytest.param('pyodide', marks=[
            pytest.mark.pyodide,
            pytest.mark.skipif(
                not HAS_PYODIDE,
                reason="pyodide not found, run npm i")
        ]),
    ])
    def llwasm_backend(self, request):
        return request.param

    @pytest.fixture
    def init_llwasm(self, request, llwasm_backend, runtime):
        # XXX: the "runtime" fixture is a temporary hack which hopefully we'll
        # be able to remove soon.
        #
        # It is provided by pytest_pyodide and its valude is "node". Ideally,
        # we would like to request it ONLY when llwasm_backend=='pyodide', but
        # we couldn't find a way to do that.
        #
        # If we don't require "runtime" in the function signature, the
        # "getfixturevalue('selenium')" below fails with the following
        # message:
        # The requested fixture has no parameter defined for test:
        #     spy/tests/test_llwasm.py::TestLLWasm::test_call[pyodide]
        self.llwasm_backend = llwasm_backend
        if self.llwasm_backend == 'pyodide':
            self.selenium = request.getfixturevalue('selenium')
            self.run_in_pyodide_maybe = run_in_pyodide
            self.toolchain = EmscriptenToolchain('debug')
        else:
            self.selenium = None
            self.run_in_pyodide_maybe = lambda fn: fn

    def test_call(self):
        src = r"""
        int add(int x, int y) {
            return x+y;
        }
        """
        test_wasm = self.compile_wasm(src, exports=['add'])

        @self.run_in_pyodide_maybe
        def fn(selenium, test_wasm):
            from spy.llwasm import LLWasmInstance

            ll = LLWasmInstance.from_file(test_wasm)
            assert ll.call('add', 4, 8) == 12

        fn(self.selenium, test_wasm)

    @pytest.mark.skip(reason='fixme')
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
            from spy.llwasm import LLWasmInstance

            ll = LLWasmInstance.from_file(test_wasm)
            exports = ll.all_exports()
            exports.sort()
            assert exports == ['_initialize', 'add', 'memory', 'x', 'y']

        fn(selenium, test_wasm)

    def test_read_global(self, selenium):
        src = r"""
        #include <stdint.h>
        int32_t x = 100;
        int16_t y = 200;
        int16_t z = 300;
        """
        test_wasm = self.compile(src, exports=['x', 'y', 'z'])
        @run_in_pyodide
        def fn(selenium, test_wasm):
            from spy.llwasm import LLWasmInstance

            ll = LLWasmInstance.from_file(test_wasm)
            assert ll.read_global('x', 'int32_t') == 100
            assert ll.read_global('y', 'int16_t') == 200
            assert ll.read_global('z', 'int16_t') == 300

        fn(selenium, test_wasm)

    def test_read_mem(self, selenium):
        src = r"""
        #include <stdint.h>
        const char *hello = "hello";
        int32_t foo[] = {100, 200};
        """
        test_wasm = self.compile(src, exports=['hello', 'foo'])
        @run_in_pyodide
        def fn(selenium, test_wasm):
            from spy.llwasm import LLWasmInstance

            ll = LLWasmInstance.from_file(test_wasm)
            ptr = ll.read_global('hello', 'void *')
            assert ll.mem.read(ptr, 6) == b'hello\0'

            ptr = ll.read_global('foo')
            assert ll.mem.read_i32(ptr) == 100
            assert ll.mem.read_i32(ptr+4) == 200

        fn(selenium, test_wasm)

    def test_write_mem(self, selenium):
        src = r"""
        #include <stdint.h>
        int8_t foo[] = {10, 20, 30};
        int32_t foo_total(void) {
            return foo[0] + foo[1] + foo[2];
        }
        """
        test_wasm = self.compile(src, exports=['foo', 'foo_total'])
        @run_in_pyodide
        def fn(selenium, test_wasm):
            from spy.llwasm import LLWasmInstance

            ll = LLWasmInstance.from_file(test_wasm)
            assert ll.call('foo_total') == 60
            #
            ptr = ll.read_global('foo')
            ll.mem.write(ptr, bytearray([40, 50, 60]))
            assert ll.call('foo_total') == 150
            #
            ll.mem.write_i8(ptr, 100)
            assert ll.call('foo_total') == 210

        fn(selenium, test_wasm)


    def test_multiple_instances(self, selenium):
        src = r"""
        int x = 100;
        int inc(void) {
            return ++x;
        }
        """
        test_wasm = self.compile(src, exports=['inc'])
        @run_in_pyodide
        def fn(selenium, test_wasm):
            from spy.llwasm import LLWasmInstance, LLWasmModule

            llmod = LLWasmModule(str(test_wasm))
            ll1 = LLWasmInstance(llmod)
            ll2 = LLWasmInstance(llmod)
            assert ll1.call('inc') == 101
            assert ll1.call('inc') == 102
            assert ll1.call('inc') == 103
            #
            assert ll2.call('inc') == 101
            assert ll2.call('inc') == 102
            assert ll2.call('inc') == 103

        fn(selenium, test_wasm)

    def test_HostModule(self, selenium):
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
        @run_in_pyodide
        def fn(selenium, test_wasm):
            from spy.llwasm import LLWasmInstance, LLWasmModule, HostModule
            llmod = LLWasmModule(str(test_wasm))

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

        fn(selenium, test_wasm)
