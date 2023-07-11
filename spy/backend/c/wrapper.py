import struct
from typing import Any
from py.path import LocalPath
import wasmtime
from spy.vm.module import W_Module
from spy.vm.function import W_Function, W_FunctionType
from spy.vm.vm import SPyVM

class WasmModuleWrapper:
    vm: SPyVM
    w_mod: W_Module
    name: str
    store: wasmtime.Store
    module: wasmtime.Module
    instance: wasmtime.Instance
    memory: wasmtime.Memory

    def __init__(self, vm: SPyVM, w_mod: W_Module, f: LocalPath) -> None:
        self.vm = vm
        self.w_mod = w_mod
        self.name = f.purebasename
        self.store = wasmtime.Store()
        self.module = wasmtime.Module.from_file(self.store.engine, str(f))
        self.instance = wasmtime.Instance(self.store, self.module, [])
        memory = self.instance.exports(self.store).get('memory')
        assert isinstance(memory, wasmtime.Memory)
        self.memory = memory

    def __repr__(self) -> str:
        return f"<WasmModuleWrapper 'self.name'>"

    def __getattr__(self, name: str) -> Any:
        exports = self.instance.exports(self.store)
        wasm_obj = exports.get(name)
        if wasm_obj is None:
            raise AttributeError(name)
        elif isinstance(wasm_obj, wasmtime.Func):
            return self.read_function(name, wasm_obj)
        elif isinstance(wasm_obj, wasmtime.Global):
            return self.read_global(name, wasm_obj)
        else:
            t = type(wasm_obj)
            raise NotImplementedError(f'Unknown WASM object: {t}')


    def read_function(self, name: str, f: wasmtime.Func) -> 'WasmFuncWrapper':
        w_func = self.w_mod.content.get(name)
        assert isinstance(w_func, W_Function)
        return WasmFuncWrapper(self.vm, w_func.w_functype, self.store, f)

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
        addr = g.value(self.store)
        assert isinstance(addr, int)
        rawbytes = self.memory.read(self.store, addr, addr+4)
        return struct.unpack('i', rawbytes)[0]


class WasmFuncWrapper:
    vm: SPyVM
    w_functype: W_FunctionType
    store: wasmtime.Store
    f: wasmtime.Func

    def __init__(self, vm: SPyVM, w_functype: W_FunctionType,
                 store: wasmtime.Store, f: wasmtime.Func) -> None:
        self.vm = vm
        self.w_functype = w_functype
        self.store = store
        self.f = f

    def __call__(self, *args: Any) -> Any:
        res = self.f(self.store, *args)
        # wasmtime doesn't distinguish between ints and bools, but we
        # do. Let's try to fix that
        if self.w_functype.w_restype is self.vm.builtins.w_bool:
            return bool(res)
        return res
