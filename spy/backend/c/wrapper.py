from typing import Any
from py.path import LocalPath
import wasmtime as w


class WasmModuleWrapper:

    def __init__(self, wasmfile: LocalPath) -> None:
        store = w.Store()
        module = w.Module.from_file(store.engine, str(wasmfile))
        instance = w.Instance(store, module, [])
        exports = instance.exports(store)
        for name, wasm_func in exports._extern_map.items():
            wasm_func_wrapper = WasmFuncWrapper(store, wasm_func)
            setattr(self, name, wasm_func_wrapper)


class WasmFuncWrapper:
    _store: w.Store
    _wasm_func: Any

    def __init__(self, store: w.Store, wasm_func: Any) -> None:
        self._store = store
        self._wasm_func = wasm_func

    def __call__(self, *args: Any) -> Any:
        return self._wasm_func(self._store, *args)
