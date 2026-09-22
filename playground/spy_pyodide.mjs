// Run spy EXACTLY like the web playground, but from the command line via
// Node + Pyodide downloaded from the CDN.
//
// This script reproduces the playground environment faithfully:
//   - Pyodide is downloaded from the jsDelivr CDN (same version as PyScript)
//   - spylang is micropip-installed from playground/spylang-*.whl
//   - libspy is installed from playground/libspy.{mjs,wasm}
//
// Node cannot import()/fetch the Pyodide runtime over https:// (the ESM loader
// only supports file: and data: URLs, and pyodide.asm.js is imported by
// relative path). So we download the runtime files into a local cache dir on
// first run and point indexURL at that dir. Delete .pyodide-cache/ to refetch.
//
// Usage (or use the ./spy_pyodide.sh wrapper):
//   node spy_pyodide.mjs <file.spy> [extra spy args...]
//   node spy_pyodide.mjs ../examples/1_high_level/hello.spy
//   node spy_pyodide.mjs redshift ../examples/1_high_level/hello.spy

import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

// Must match the Pyodide version bundled by the PyScript release used in
// index.html (see playground/index.html). Pyodide 0.27.7 ships with
// PyScript 2026.1.1 and matches pyodide/node_modules/pyodide.
const PYODIDE_VERSION = "0.27.7";
const CDN = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

const HERE = dirname(fileURLToPath(import.meta.url));
const CACHE_DIR = join(HERE, ".pyodide-cache", `v${PYODIDE_VERSION}`);

// The minimal set of runtime files loadPyodide() needs, plus the micropip
// package (and its deps) so micropip.install() works offline against the cache.
const RUNTIME_FILES = [
  "pyodide.mjs",
  "pyodide.asm.js",
  "pyodide.asm.wasm",
  "python_stdlib.zip",
  "pyodide-lock.json",
  "micropip-0.9.0-py3-none-any.whl",
  "packaging-24.2-py3-none-any.whl",
];

function findWheel() {
  const wheels = readdirSync(HERE).filter(
    (f) => f.startsWith("spylang-") && f.endsWith(".whl"),
  );
  if (wheels.length === 0) {
    throw new Error(`no spylang-*.whl found in ${HERE}; run 'make local' first`);
  }
  return wheels[0];
}

async function ensureRuntimeCache() {
  mkdirSync(CACHE_DIR, { recursive: true });
  for (const name of RUNTIME_FILES) {
    const dest = join(CACHE_DIR, name);
    if (existsSync(dest)) {
      continue;
    }
    console.log(`[node] downloading ${name} from CDN...`);
    const res = await fetch(CDN + name);
    if (!res.ok) {
      throw new Error(`failed to download ${name}: ${res.status}`);
    }
    const buf = Buffer.from(await res.arrayBuffer());
    writeFileSync(dest, buf);
  }
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.error("usage: node run_pyodide.mjs <file.spy> [extra spy args...]");
    process.exit(2);
  }

  const wheel = findWheel();
  const libspyMjs = join(HERE, "libspy.mjs");
  if (!existsSync(libspyMjs)) {
    throw new Error(`${libspyMjs} not found; run 'make local' first`);
  }

  await ensureRuntimeCache();

  const { loadPyodide } = await import(
    pathToFileURL(join(CACHE_DIR, "pyodide.mjs")).href
  );
  const pyodide = await loadPyodide({ indexURL: CACHE_DIR });

  // Mount the repo root so the wheel, libspy and the .spy file are reachable
  // from inside Pyodide by the same relative paths the user typed.
  const repoRoot = resolve(HERE, "..");
  pyodide.FS.mkdir("/repo");
  pyodide.FS.mount(pyodide.FS.filesystems.NODEFS, { root: repoRoot }, "/repo");
  pyodide.FS.chdir("/repo/playground");

  await pyodide.loadPackage("micropip");

  // libspy is loaded by Node's import(), which runs against the *host*
  // filesystem (see spy/llwasm/emscripten.py), so it needs the host path.
  pyodide.globals.set("LIBSPY_MJS_HOST_PATH", libspyMjs);
  pyodide.globals.set("WHEEL_NAME", wheel);
  pyodide.globals.set("SPY_ARGV", args);

  await pyodide.runPythonAsync(`
import micropip
await micropip.install(f"emfs:/repo/playground/{WHEEL_NAME}")

import spy.cli
from spy import libspy

# Use the release libspy shipped in playground/, exactly like main.py does.
libspy.LIBSPY_WASM = LIBSPY_MJS_HOST_PATH

try:
    spy.cli.app(list(SPY_ARGV))
except SystemExit:
    pass
`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
