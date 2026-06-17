import os
import textwrap

import py.path
import pytest
from pytest_pyodide import run_in_pyodide  # type: ignore

import spy.libspy as libspy
from spy import ROOT
from spy.build.build_info import BuildType
from spy.build.flags import get_ar, get_cflags
from spy.build.wasm_bundle import get_or_build_bundle, link_bundle
from spy.libspy import LLSPyInstance
from spy.llwasm import LLWasmInstance
from spy.tests.support import CTest
from spy.util import robust_run

PYODIDE = ROOT.join("..", "pyodide", "node_modules", "pyodide")
HAS_PYODIDE = PYODIDE.check(exists=True)


@pytest.mark.usefixtures("init_llwasm")
class TestLLWasm(CTest):
    @pytest.fixture(
        params=[
            # "normal" execution, under CPython
            pytest.param("wasmtime", marks=pytest.mark.wasmtime),
            # run tests inside pyodide, using the 'emscripten' llwasm backend
            pytest.param(
                "pyodide",
                marks=[
                    pytest.mark.pyodide,
                    pytest.mark.skipif(
                        not HAS_PYODIDE, reason="pyodide not found, run npm i"
                    ),
                ],
            ),
        ]
    )
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
        self.llwasm_backend = llwasm_backend  # type: ignore
        if self.llwasm_backend == "pyodide":
            self.selenium = request.getfixturevalue("selenium")
            self.run_in_pyodide_maybe = run_in_pyodide
            self.target = "emscripten"
        else:
            self.selenium = None
            self.run_in_pyodide_maybe = lambda fn: fn

    def test_call(self):
        src = r"""
        int add(int x, int y) {
            return x+y;
        }
        """
        test_wasm = self.c_compile(src, exports=["add"])

        @self.run_in_pyodide_maybe
        def fn(selenium, test_wasm):
            from spy.llwasm import LLWasmInstance

            ll = LLWasmInstance.from_file(test_wasm)
            assert ll.call("add", 4, 8) == 12

        fn(self.selenium, test_wasm)

    def test_all_exports(self):
        if self.llwasm_backend == "pyodide":
            pytest.skip("fixme")

        src = r"""
        int add(int x, int y) {
            return x+y;
        }
        int x;
        int y;
        """
        test_wasm = self.c_compile(src, exports=["add", "x", "y"])

        @self.run_in_pyodide_maybe
        def fn(selenium, test_wasm):
            from spy.llwasm import LLWasmInstance

            ll = LLWasmInstance.from_file(test_wasm)
            exports = ll.all_exports()
            assert {"_initialize", "add", "memory", "x", "y"}.issubset(exports)

        fn(self.selenium, test_wasm)

    def test_read_global(self):
        src = r"""
        #include <stdint.h>
        int32_t x = 100;
        int16_t y = 200;
        int16_t z = 300;
        """
        test_wasm = self.c_compile(src, exports=["x", "y", "z"])

        @self.run_in_pyodide_maybe
        def fn(selenium, test_wasm):
            from spy.llwasm import LLWasmInstance

            ll = LLWasmInstance.from_file(test_wasm)
            assert ll.read_global("x", "int32_t") == 100
            assert ll.read_global("y", "int16_t") == 200
            assert ll.read_global("z", "int16_t") == 300

        fn(self.selenium, test_wasm)

    def test_read_mem(self):
        src = r"""
        #include <stdint.h>
        const char *hello = "hello";
        int32_t foo[] = {100, 200};
        """
        test_wasm = self.c_compile(src, exports=["hello", "foo"])

        @self.run_in_pyodide_maybe
        def fn(selenium, test_wasm):
            from spy.llwasm import LLWasmInstance

            ll = LLWasmInstance.from_file(test_wasm)
            ptr = ll.read_global("hello", "void *")
            assert ll.mem.read(ptr, 6) == b"hello\0"

            ptr = ll.read_global("foo")
            assert ll.mem.read_i32(ptr) == 100
            assert ll.mem.read_i32(ptr + 4) == 200

        fn(self.selenium, test_wasm)

    def test_write_mem(self):
        src = r"""
        #include <stdint.h>
        int8_t foo[] = {10, 20, 30};
        int32_t foo_total(void) {
            return foo[0] + foo[1] + foo[2];
        }
        """
        test_wasm = self.c_compile(src, exports=["foo", "foo_total"])

        @self.run_in_pyodide_maybe
        def fn(selenium, test_wasm):
            from spy.llwasm import LLWasmInstance

            ll = LLWasmInstance.from_file(test_wasm)
            assert ll.call("foo_total") == 60
            #
            ptr = ll.read_global("foo")
            ll.mem.write(ptr, bytearray([40, 50, 60]))
            assert ll.call("foo_total") == 150
            #
            ll.mem.write_i8(ptr, 100)
            assert ll.call("foo_total") == 210

        fn(self.selenium, test_wasm)

    def test_multiple_instances(self):
        src = r"""
        int x = 100;
        int inc(void) {
            return ++x;
        }
        """
        test_wasm = self.c_compile(src, exports=["inc"])

        @self.run_in_pyodide_maybe
        def fn(selenium, test_wasm):
            from spy.llwasm import LLWasmInstance, LLWasmModule

            llmod = LLWasmModule(str(test_wasm))
            ll1 = LLWasmInstance(llmod)
            ll2 = LLWasmInstance(llmod)
            assert ll1.call("inc") == 101
            assert ll1.call("inc") == 102
            assert ll1.call("inc") == 103
            #
            assert ll2.call("inc") == 101
            assert ll2.call("inc") == 102
            assert ll2.call("inc") == 103

        fn(self.selenium, test_wasm)

    def c_compile_archive(
        self,
        src: str,
        *,
        name: str,
        build_type: BuildType = "debug",
    ) -> py.path.local:
        assert self.target == "wasi", "c_compile_archive only supports wasi target"
        src = textwrap.dedent(src)
        c_file = self.tmpdir.join(f"{name}.c")
        o_file = self.tmpdir.join(f"{name}.o")
        a_file = self.tmpdir.join(f"{name}.a")
        c_file.write(src)

        cflags = get_cflags(self.target, build_type)
        cc = ["python", "-m", "ziglang", "cc"]
        robust_run(
            [
                *cc,
                *cflags,
                "-c",
                str(c_file),
                "-o",
                str(o_file),
            ]
        )

        ar = get_ar(self.target).split()
        robust_run([*ar, "rcs", str(a_file), str(o_file)])
        return a_file

    def wasm_link_bundle(
        self,
        archives: list[py.path.local],
        *,
        name: str = "bundle",
    ) -> py.path.local:
        out = self.tmpdir.join(f"{name}.wasm")
        link_bundle(archives, out=out)
        return out

    def test_bundle_multiple_archives(self):
        if self.llwasm_backend == "pyodide":
            pytest.skip("emscripten bundling not yet implemented")

        part_a_src = """
        #include <stdint.h>
        #include "spy.h"
        int32_t shared_x = 100;
        int32_t WASM_EXPORT(a_get_shared)(void) { return shared_x; }
        int32_t WASM_EXPORT(a_inc)(void) { return ++shared_x; }
        """

        part_b_src = """
        #include <stdint.h>
        #include "spy.h"
        extern int32_t shared_x;
        int32_t WASM_EXPORT(b_get_shared)(void) { return shared_x; }
        int32_t WASM_EXPORT(b_double)(void) { shared_x *= 2; return shared_x; }
        """

        a_a = self.c_compile_archive(part_a_src, name="part_a")
        b_a = self.c_compile_archive(part_b_src, name="part_b")

        bundle = self.wasm_link_bundle(archives=[a_a, b_a])

        ll = LLWasmInstance.from_file(bundle)

        assert ll.call("a_get_shared") == 100
        assert ll.call("b_get_shared") == 100

        assert ll.call("a_inc") == 101
        assert ll.call("b_double") == 202
        assert ll.call("a_get_shared") == 202

    def test_bundle_cache(self):
        if self.llwasm_backend == "pyodide":
            pytest.skip("emscripten bundling not yet implemented")

        src = """
        #include <stdint.h>
        #include "spy.h"
        int32_t WASM_EXPORT(answer)(void) { return 42; }
        """
        a = self.c_compile_archive(src, name="answer")
        bundle1 = get_or_build_bundle([a])
        mtime1 = bundle1.mtime()
        bundle2 = get_or_build_bundle([a])
        assert bundle1 == bundle2
        assert bundle2.mtime() == mtime1
        bundle3 = get_or_build_bundle([a], force_rebuild=True)
        assert bundle3 == bundle1
        assert bundle3.mtime() >= mtime1

    def test_bundle_cache_invalidation(self):
        if self.llwasm_backend == "pyodide":
            pytest.skip("emscripten bundling not yet implemented")

        src_v1 = """
        #include <stdint.h>
        #include "spy.h"
        int32_t WASM_EXPORT(answer)(void) { return 42; }
        """
        src_v2 = """
        #include <stdint.h>
        #include "spy.h"
        int32_t WASM_EXPORT(answer)(void) { return 99; }
        """
        a_v1 = self.c_compile_archive(src_v1, name="answer_v1")
        a_v2 = self.c_compile_archive(src_v2, name="answer_v2")
        bundle_v1 = get_or_build_bundle([a_v1])
        bundle_v2 = get_or_build_bundle([a_v2])
        assert bundle_v1 != bundle_v2

    def test_get_LLMOD_with_extra_archive(self):
        if self.llwasm_backend == "pyodide":
            pytest.skip("emscripten bundling not yet implemented")

        # An out-of-tree archive that calls spy_str_alloc from libspy.
        # This test verifies that a side archive can #include "spy.h" and call
        # libspy functions when bundled together.
        src = r"""
        #include "spy.h"
        #include "spy/str.h"
        #include <string.h>

        spy_StrObject * WASM_EXPORT(make_hello)(void) {
            const char *msg = "hello";
            size_t n = strlen(msg);
            spy_StrObject *s = spy_str_alloc(n);
            memcpy(spy_StrObject_UTF8(s), msg, n);
            return s;
        }
        """
        extra_a = self.c_compile_archive(src, name="side_str")
        # make_hello is annotated with WASM_EXPORT so it is exported automatically
        llmod = libspy.get_LLMOD(extra_archives=[extra_a])
        ll = LLSPyInstance(llmod)

        ptr = ll.call("make_hello")
        length, _, utf8 = ll.read_str(ptr)
        assert utf8 == b"hello"
        assert length == 5

    def test_HostModule(self):
        if self.llwasm_backend == "pyodide":
            pytest.skip("fixme")

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
        test_wasm = self.c_compile(src, exports=["compute"])

        @self.run_in_pyodide_maybe
        def fn(selenium, test_wasm):
            from spy.llwasm import HostModule, LLWasmInstance, LLWasmModule

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
            assert ll.call("compute") == 900
            assert recorder.log == [100, 200]

        fn(self.selenium, test_wasm)
