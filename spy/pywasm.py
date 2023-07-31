"""
A pythonic wrapper around wasmtime
"""

from typing import Any, Optional, Literal
import py.path
import wasmtime
import struct

ENGINE = wasmtime.Engine()

WasmType = Literal[None, 'void *', 'int32_t', 'int16_t']

class LLWasmModule:
    f: py.path.local
    mod: wasmtime.Module

    def __init__(self, f: py.path.local) -> None:
        self.f = f
        self.mod = wasmtime.Module.from_file(ENGINE, str(f))

    def __repr__(self) -> str:
        return '<LLWasmModule {self.f}>'

    def instantiate(self) -> 'LLWasmInstance':
        store = wasmtime.Store(ENGINE)
        inst = wasmtime.Instance(store, self.mod, [])
        return LLWasmInstance(self.f, store, inst)


class LLWasmInstance:
    f: py.path.local
    store: wasmtime.Store
    instance: wasmtime.Instance
    memory: wasmtime.Memory

    def __init__(self, f: py.path.local, store: wasmtime.Store,
                 instance: wasmtime.Instance) -> None:
        self.f = f
        self.store = store
        self.instance = instance
        memory = self.instance.exports(store).get('memory')
        assert isinstance(memory, wasmtime.Memory)
        self.memory = memory

    @staticmethod
    def from_file(f: py.path.local) -> 'LLWasmInstance':
        return LLWasmModule(f).instantiate()

    def get_export(self, name: str) -> Any:
        exports = self.instance.exports(self.store)
        wasm_obj = exports.get(name)
        if wasm_obj is None:
            raise AttributeError(name)
        return wasm_obj

    def all_exports(self) -> Any:
        exports = self.instance.exports(self.store)
        return list(exports._extern_map)

    def call(self, name: str, *args: Any) -> Any:
        func = self.get_export(name)
        assert isinstance(func, wasmtime.Func)
        return func(self.store, *args)

    def read_global(self, name: str, deref: WasmType = None) -> Any:
        """
        Read the given global.

        The semantics is a bit unfortunately: currently, clang always store C
        globals in linear memory, meaning that the corresponding WASM global
        contains a *pointer* to the memory.

        clang has plans to support "real" WASM globals: see
        https://github.com/emscripten-core/emscripten/issues/12793

        If we are reading a scalar, we most likely want to deref the pointer
        and cast the bytes to the desired type. However, in some cases we are
        interested in the address, e.g. if the global points to an array or a
        struct: in that case, we can pass deref=None.

        For example, the following C program:
            int16_t a = 0xAAAA;
            int16_t b[] = {0xBBBB, 0xCCCC};

        Produces the following WASM:
            (global $a i32 (i32.const 1024))
            (global $b i32 (i32.const 1026))
            (data $d0 (i32.const 1024) "\aa\aa\bb\bb\cc\cc")

        In this case:
            read_global('a', deref=None) == 1024
            read_global('b', deref=None) == 1026
            read_global('a', deref='i16') == 0xAAAA
            read_global('b', deref='i16') == 0xBBBB # first item of the array
        """
        g = self.get_export(name)
        assert isinstance(g, wasmtime.Global)
        addr = g.value(self.store)
        assert isinstance(addr, int)
        if deref is None:
            return addr
        elif deref == 'int32_t' or deref == 'void *':
            return self.read_mem_i32(addr)
        elif deref == 'int16_t':
            return self.read_mem_i16(addr)
        else:
            assert False, f'Unknown type: {deref}'

    def read_mem(self, addr: int, n: int) -> bytearray:
        """
        Read n bytes of memory at the given address.
        """
        return self.memory.read(self.store, addr, addr+n)

    def read_mem_i32(self, addr: int) -> int:
        rawbytes = self.read_mem(addr, 4)
        return struct.unpack('i', rawbytes)[0]

    def read_mem_i16(self, addr: int) -> int:
        rawbytes = self.read_mem(addr, 2)
        return struct.unpack('h', rawbytes)[0]

    def write_mem(self, addr: int, b: bytes) -> None:
        self.memory.write(self.store, b, addr)
