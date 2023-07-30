"""
A pythonic wrapper around wasmtime
"""

from typing import Any, Optional
import py.path
import wasmtime
import struct

ENGINE = wasmtime.Engine()

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
    def from_file(f: py.path.local) -> 'WasmInstance':
        return LLWasmModule(f).instantiate()

    def get_export(self, name: str) -> Any:
        exports = self.instance.exports(self.store)
        wasm_obj = exports.get(name)
        if wasm_obj is None:
            raise AttributeError(name)
        return wasm_obj

    ## def all_exports(self) -> Any:
    ##     exports = self.instance.exports(self.store)

    def call(self, name: str, *args: Any) -> Any:
        func = self.get_export(name)
        assert isinstance(func, wasmtime.Func)
        return func(self.store, *args)

    def read_mem(self, addr: int, n: int) -> bytearray:
        """
        Read n bytes of memory at the given address.
        """
        return self.memory.read(self.store, addr, addr+n)

    def read_mem_i32(self, addr: int) -> int:
        rawbytes = self.read_mem(addr, 4)
        return struct.unpack('i', rawbytes)[0]

    def write_mem(self, addr: int, b: bytes) -> None:
        self.memory.write(self.store, b, addr)
