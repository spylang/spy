import wasmtime

class WasmModuleWrapper:

    def __init__(self, wasmfile):
        store = wasmtime.Store()
        module = wasmtime.Module.from_file(store.engine, wasmfile)
        instance = wasmtime.Instance(store, module, [])
        exports = instance.exports(store)
        for name, wasm_func in exports._extern_map.items():
            wasm_func_wrapper = WasmFuncWrapper(store, wasm_func)
            setattr(self, name, wasm_func_wrapper)

class WasmFuncWrapper:

    def __init__(self, store, wasm_func):
        self._store = store
        self._wasm_func = wasm_func

    def __call__(self, *args):
        return self._wasm_func(self._store, *args)
