// Custom instantiateWasm hook that also calls Module.adjustWasmImports(imports)
// if it is defined. This allows us to insert HostModule-defined symbols into
// imports.
//
// instantiateWasm is the only hook that Emscripten exposes after the imports
// object is created but before wasm instantiation. A previous attempt to add an
// adjustWasmImports hook upstream has not succeeded:
// https://github.com/emscripten-core/emscripten/pull/23794


// This is the logic that happens when no instantiateWasm callback is provided
// on most Emscripten settings. See here:
// https://github.com/emscripten-core/emscripten/blob/eb51a986459b585f24be38362e2227d29e0d70a1/src/preamble.js?plain=1#L935-L942
async function defaultInstantiateWasm(imports, successCallback) {
  wasmBinaryFile ??= findWasmBinary();
  const { instance, module } = await instantiateArrayBuffer(wasmBinaryFile, imports);
  successCallback(instance, module);
}


Module.instantiateWasm = (imports, successCallback) => {
  Module.adjustWasmImports?.(imports);
  defaultInstantiateWasm(imports, successCallback);
};
