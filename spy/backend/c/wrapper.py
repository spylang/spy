import struct
from typing import Any, Optional
from py.path import LocalPath
import wasmtime
from spy.vm.module import W_Module
from spy.vm.function import W_Function, W_FunctionType
from spy.vm.vm import SPyVM

class LLWasmModule:
    """
    A low-level wrapper around wasmtime. It doesn't know anything about SPy
    types, it just exposes an API which is nicer to use.
    """
    store: wasmtime.Store
    module: wasmtime.Module
    instance: wasmtime.Instance
    memory: wasmtime.Memory

    def __init__(self, f: LocalPath) -> None:
        self.name = f.purebasename
        self.store = wasmtime.Store()
        self.module = wasmtime.Module.from_file(self.store.engine, str(f))
        self.instance = wasmtime.Instance(self.store, self.module, [])
        memory = self.instance.exports(self.store).get('memory')
        assert isinstance(memory, wasmtime.Memory)
        self.memory = memory

    def get_export(self, name: str) -> Any:
        exports = self.instance.exports(self.store)
        wasm_obj = exports.get(name)
        if wasm_obj is None:
            raise AttributeError(name)
        return wasm_obj

    def call(self, name: str, *args: Any) -> Any:
        func = self.get_export(name)
        assert isinstance(func, wasmtime.Func)
        return func(self.store, *args)

    def read_mem(self, addr: int, n: int,
                 *, fmt: Optional[str] = None) -> Any:
        """
        Read n bytes of memory at the given address.

        If fmt is given, automatically unpack the raw bytes into a Python
        object using struct.unpack().
        """
        rawbytes = self.memory.read(self.store, addr, addr+n)
        if fmt is None:
            return rawbytes
        else:
            return struct.unpack(fmt, rawbytes)[0]

class WasmModuleWrapper:
    vm: SPyVM
    w_mod: W_Module
    llmod: LLWasmModule

    def __init__(self, vm: SPyVM, w_mod: W_Module, f: LocalPath) -> None:
        self.vm = vm
        self.w_mod = w_mod
        self.llmod = LLWasmModule(f)

    def __repr__(self) -> str:
        return f"<WasmModuleWrapper 'self.llmod.name'>"

    def __getattr__(self, name: str) -> Any:
        wasm_obj = self.llmod.get_export(name)
        if isinstance(wasm_obj, wasmtime.Func):
            return self.read_function(name)
        elif isinstance(wasm_obj, wasmtime.Global):
            return self.read_global(name, wasm_obj)
        else:
            t = type(wasm_obj)
            raise NotImplementedError(f'Unknown WASM object: {t}')

    def read_function(self, name: str) -> 'WasmFuncWrapper':
        w_func = self.w_mod.content.get(name)
        assert isinstance(w_func, W_Function)
        return WasmFuncWrapper(self.vm, name, w_func.w_functype, self.llmod)

    def read_global(self, name: str, g: wasmtime.Global) -> Any:
        # sigh, this is very unfortunate. Currently, there is no way to
        # convince clang to use a proper WASM global for C global variables:
        # instead, they are stored in linear memory, and so the global symbol
        # that we get contains the address.  Ideally, eventually we want to
        # fix this, but for now we simply work around by reading the linear
        # memory.
        # https://github.com/emscripten-core/emscripten/issues/12793
        #
        # XXX here we assume/hardcode that we are reading an i32
        addr = g.value(self.llmod.store)
        assert isinstance(addr, int)
        rawbytes = self.llmod.memory.read(self.llmod.store, addr, addr+4)
        return struct.unpack('i', rawbytes)[0]


class WasmFuncWrapper:
    vm: SPyVM
    name: str
    w_functype: W_FunctionType
    llmod: LLWasmModule

    def __init__(self, vm: SPyVM, name:str, w_functype: W_FunctionType,
                 llmod: LLWasmModule) -> None:
        self.vm = vm
        self.name = name
        self.w_functype = w_functype
        self.llmod = llmod

    def __call__(self, *args: Any) -> Any:
        res = self.llmod.call(self.name, *args)
        # wasmtime doesn't distinguish between ints and bools, but we
        # do. Let's try to fix that
        if self.w_functype.w_restype is self.vm.builtins.w_bool:
            return bool(res)
        return res
