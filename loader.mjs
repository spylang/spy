export async function loadModule(f) {
    const res = await import(f.replace("/spy", "."));
    return await res.emscriptenModule;
}
