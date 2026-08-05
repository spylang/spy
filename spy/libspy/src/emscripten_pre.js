Module.instantiateWasm = (imports, successCallback) => {
  (async () => {
    Module.adjustWasmImports?.(imports);
    wasmBinaryFile ??= findWasmBinary();
    const { instance } = await instantiateArrayBuffer(wasmBinaryFile, imports);
    successCallback(instance);
  })();
  return {};
};
