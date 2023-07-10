import struct
from typing import Any
from py.path import LocalPath
import wasmtime as w


class WasmModuleWrapper:
    name: str
    store: w.Store
    module: w.Module
    instance: w.Instance
    memory: w.Memory

    def __init__(self, wasmfile: LocalPath) -> None:
        self.name = wasmfile.purebasename
        self.store = w.Store()
        self.module = w.Module.from_file(self.store.engine, str(wasmfile))
        self.instance = w.Instance(self.store, self.module, [])
        self.memory = self.instance.exports(self.store).get('memory')

    def __repr__(self) -> str:
        return f"<WasmModuleWrapper 'self.name'>"

    def __getattr__(self, name: str) -> Any:
        exports = self.instance.exports(self.store)
        wasm_obj = exports.get(name)
        if wasm_obj is None:
            raise AttributeError(name)
        elif isinstance(wasm_obj, w.Func):
            return WasmFuncWrapper(self.store, wasm_obj)
        elif isinstance(wasm_obj, w.Global):
            return self.read_global(wasm_obj)
        else:
            t = type(wasm_obj)
            raise NotImplementedError(f'Unknown WASM object: {t}')

    def read_global(self, g: w.Global) -> Any:
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
        rawbytes = self.memory.read(self.store, addr, addr+4)
        return struct.unpack('i', rawbytes)[0]


class WasmFuncWrapper:
    _store: w.Store
    _wasm_func: w.Func

    def __init__(self, store: w.Store, wasm_func: w.Func) -> None:
        self._store = store
        self._wasm_func = wasm_func

    def __call__(self, *args: Any) -> Any:
        return self._wasm_func(self._store, *args)
