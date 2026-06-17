# llwasm: the low-level WASM layer

/// admonition | AI-generated document
    type: note

This document was generated in large parts by an AI assistant. It has been reviewed by a
human and found accurate and useful enough to be committed to the repository.
///


`spy/llwasm/` is a small Python package which abstracts the loading,
linking and instantiation of WebAssembly modules. The rest of SPy never
talks to a WASM runtime directly: it always goes through `llwasm`.

It is called "LL" for two reasons:

  - it exposes a *low-level* view on the code: there is no concept of
    "string" or "object", only ints, floats and raw bytes of linear memory;

  - it's an unused prefix: other prefixes such as `Py`, `Wasm`, `W` would
    have been very confusing.

The main consumer of `llwasm` is the SPy interpreter itself: each `SPyVM`
owns an instance of `libspy.wasm` (available as `vm.ll`), and all non-scalar
objects (e.g. strings and bytes) live inside its linear memory, even in
interpreted mode. This is a deliberate design choice: interpreted and
compiled SPy code manipulate *the same* C data structures.

`vm.ll` always wraps exactly **one** WASM module. Usually that module is
`libspy.wasm`, but when the VM loads out-of-tree builtin modules (e.g.
wrappers of existing C libraries) it instead wraps a *bundle*: a single
WASM module produced by statically linking libspy together with the
out-of-tree modules' archives ahead of time. See
[Out-of-tree builtin modules](#out-of-tree-builtin-modules) for how this
works.

## The big picture

```
┌───────────────────────────────────────────────────────────────┐
│                    Python interpreter (host)                  │
│                                                               │
│   SPyVM ──── vm.ll ───► LLSPyInstance        (spy.libspy)     │
│                              │  adds LibSPyHost, knows the    │
│                              │  layout of str/bytes objects   │
│                              ▼                                │
│                         LLWasmInstance       (spy.llwasm)     │
│                              │  abstracts the WASM runtime    │
│              ┌───────────────┴────────────────┐               │
│              ▼                                ▼               │
│      wasmtime backend                 emscripten backend      │
│      (normal CPython)               (CPython-inside-Pyodide)  │
└──────────────┬────────────────────────────────┬───────────────┘
               ▼                                ▼
          libspy.wasm                      libspy.mjs
       (wasi, zig cc)                  (emscripten, emcc)
```

There are two independent axes to keep in mind:

  1. **Which WASM runtime executes the code.** When SPy runs on normal
     CPython, WASM code is executed by
     [wasmtime](https://github.com/bytecodealliance/wasmtime-py). When SPy
     itself runs inside the browser (i.e. on top of
     [Pyodide](https://pyodide.org)), we cannot use wasmtime: instead we use
     the JS engine's own WASM support, through Emscripten-generated
     JavaScript glue code.

  2. **Which WASM binary is loaded.** Usually it's `libspy.wasm` (the SPy
     runtime library written in C), but the same machinery is used by the
     test suite to load and call WASM modules produced by the C backend.

## Module structure

```
spy/llwasm/
├── __init__.py      # picks the backend at import time
├── base.py          # abstract API + shared helpers
├── wasmtime.py      # backend for normal CPython
└── emscripten.py    # backend for CPython-inside-Pyodide
```

The backend is selected *at import time*, based on
`spy.platform.IS_PYODIDE`:

```python
if not TYPE_CHECKING and IS_PYODIDE:
    from .emscripten import LLWasmInstance, LLWasmMemory, LLWasmModule, WasmTrap
else:
    from .wasmtime import LLWasmInstance, LLWasmMemory, LLWasmModule, WasmTrap
```

Both backends implement the same interface, defined in `base.py`. The rest
of the codebase imports from `spy.llwasm` and doesn't care which backend is
active.

## Core concepts

`base.py` defines four classes. The key distinction is between a *module*
(stateless, compiled code) and an *instance* (live state):

`LLWasmModule`
:   Wraps the **compiled code** of a `.wasm` file. It is stateless: it has
    no memory, no globals, nothing to mutate. Loading and compiling a WASM
    module is relatively expensive, so this is meant to be done **once per
    process** and shared.

`LLWasmInstance`
:   A **live instantiation** of an `LLWasmModule`: it owns the linear
    memory and the mutable state, and exposes the module's exports
    (functions and globals) to Python. You can instantiate the same
    `LLWasmModule` many times, and each instance gets its own private
    memory. This is meant to be done **once per `SPyVM`**.

`LLWasmMemory`
:   A thin wrapper around the instance's linear memory, with typed
    read/write helpers: `read_i32`, `write_i32`, `read_f64`, `read_cstr`,
    `read_ptr`, etc. Addresses are just integers (offsets into the linear
    memory).

`HostModule`
:   The mechanism to expose **Python functions to WASM code**. WASM modules
    can declare imports; a `HostModule` subclass provides them as methods
    whose name encodes the import they implement (e.g. the method
    `env_spy_debug_log` implements the import `spy_debug_log` from the
    `env` namespace). After instantiation, the host module gets a
    back-reference `self.ll` to the `LLWasmInstance`, so its methods can
    read WASM memory (e.g. to decode a `char *` argument).

The dataflow between host and guest looks like this:

```
        Python (host)                          WASM (guest)
 ───────────────────────────────       ─────────────────────────────
  ll.call("spy_str_alloc", n)   ────►  exported function
  ll.read_global("foo", ...)    ────►  exported global
  ll.mem.read(addr, n)          ────►  linear memory
  ll.mem.write(addr, b)         ────►  linear memory
  hostmod.env_spy_debug_log     ◄────  import "env" "spy_debug_log"
```

### A note on C globals

`LLWasmInstance.read_global` deserves a special mention because the
semantics is a bit unfortunate: clang always stores C globals in linear
memory, so the corresponding WASM global contains a *pointer* to the
memory, not the value itself. `read_global(name, deref='int32_t')` reads
the WASM global to get the address, then dereferences it. With
`deref=None` you get the address itself, which is what you want if the
global is an array or a struct.

## The wasmtime backend

`wasmtime.py` is the backend used on normal CPython, and the easiest to
understand. The relevant wasmtime concepts map 1:1 onto llwasm:

```
LLWasmModule                          LLWasmInstance
├── filename                          ├── llmod ──► LLWasmModule (shared)
└── mod: wt.Module (compiled code)    ├── store: wt.Store    (runtime state)
                                      ├── instance: wt.Instance  (exports)
        one per process               └── mem: LLWasmMemory  (linear memory)

                                              one per SPyVM
```

A few things worth noting:

  - There is a single, lazily-created `wt.Engine` per process. It **must
    not** be created at import time: the engine installs signal handlers to
    catch WASM traps, and if it is created too early, pytest's
    `faulthandler` can overwrite them, turning traps into hard crashes (see
    PR #378).

  - Each `LLWasmInstance` creates its own `wt.Store`. The store is the
    container of *all* runtime state in wasmtime: instances belonging to
    different stores cannot see each other.

  - Linking happens in `get_linker()`: the module is linked against WASI
    (with inherited stdin/stdout/stderr and a preopened `/`, so WASM code
    can do I/O on the host filesystem) and against the provided
    `HostModule`s. For each import `(module, name)` declared by the WASM
    module, the linker looks for a method called `{module}_{name}` on the
    host modules; its WASM signature is derived from the Python type
    annotations. Imports that nobody provides are bound to a stub which
    raises `NotImplementedError` if actually called: this way a module with
    unresolved imports can still be instantiated, as long as it doesn't
    call them.

  - `libspy.wasm` is a WASI **reactor**: a library-style module with no
    `main`. Reactors export a `_initialize` function which sets up the C
    runtime; `LLWasmInstance.__init__` calls it right after instantiation.

## The emscripten backend

`emscripten.py` is used when SPy itself runs inside Pyodide (in the browser
or under node). Here we don't control the WASM runtime: the JS engine does
the actual instantiation, and we drive it through the JavaScript "glue
code" generated by Emscripten.

The compiled artifact is not a bare `.wasm` file but a `.mjs` JavaScript
module (e.g. `libspy.mjs`) which embeds/loads the WASM and exports a
*factory function*. The mapping is:

  - `LLWasmModule` wraps the **factory** (obtained with a JS dynamic
    `import()` of the `.mjs` URL);

  - `LLWasmInstance` wraps the **Emscripten module object** returned by
    calling the factory. Exports are reached as attributes with a leading
    underscore (`instance._spy_str_alloc`), and the linear memory is the
    `HEAP8` typed array.

Host modules work differently too: we can't build the import object
ourselves, so we pass an `adjustWasmImports` callback to the factory.
Emscripten generates stub functions for undefined symbols (we link with
`-sERROR_ON_UNDEFINED_SYMBOLS=0`); the callback walks the `env` imports and
replaces each stub with the corresponding `env_*` method found on the host
modules.

### Sync vs async instantiation

In JS, fetching and instantiating WASM is inherently asynchronous. Under
node we can use `pyodide.ffi.run_sync` to block on the promise, so the
normal synchronous constructors work. In the browser we cannot block the
main thread: that's why `LLWasmModule`, `LLWasmInstance` (and, further up,
`SPyVM`) all provide an `async_new` classmethod. The wasmtime backend
implements `async_new` too (trivially, since nothing is actually async),
so callers can be written once for both backends.

## libspy: the C runtime

`spy/libspy/` contains the SPy runtime library, written in C: string and
bytes objects, builtins, the `unsafe` helpers, panic handling, etc. The
same sources are compiled to several targets (see `spy/libspy/Makefile`):

| target          | artifact      | compiler | used by                            |
|-----------------|---------------|----------|------------------------------------|
| `wasi`          | `libspy.wasm` | zig cc   | `vm.ll` on normal CPython          |
| `emscripten`    | `libspy.mjs`  | emcc     | `vm.ll` under Pyodide              |
| `native`        | `libspy.a`    | cc       | `spy -c`, native executables       |
| `native-static` | `libspy.a`    | zig cc   | statically-linked executables      |

Note that only the first two are related to `llwasm`: when SPy code is
compiled to a *native* executable, `libspy.a` is linked in the usual C way
and no WASM is involved at all.

On top of the C library, the Python package `spy.libspy` provides the
SPy-specific layer over llwasm:

`LLMOD`
:   The global `LLWasmModule` for `libspy.wasm`. This is the "done once per
    process" part: on normal CPython it is preloaded at import time; under
    Pyodide it is loaded lazily (and asynchronously) by
    `async_get_LLMOD()`.

`get_LLMOD(extra_archives, extra_exports)`
:   Returns the `LLWasmModule` to instantiate for a VM. With no extra
    archives it just returns the global `LLMOD`; with extra archives it
    builds (or reuses from cache) a *bundle* that statically links libspy
    with the out-of-tree modules. See
    [Out-of-tree builtin modules](#out-of-tree-builtin-modules).

`LibSPyHost`
:   The `HostModule` providing the imports that libspy's C code expects
    from the outside world: debug logging (`env_spy_debug_log`) and panic
    reporting (`env_spy_debug_set_panic_message`). When the C code panics,
    it records the error type, message and location via this host module
    and then executes a WASM trap.

`LLSPyInstance`
:   A subclass of `LLWasmInstance` which automatically links a fresh
    `LibSPyHost`, and queries the WASM module for the memory layout of
    `spy_StrObject` and `spy_BytesObject` (by calling the exported
    `_spy_StrObject_layout` / `_spy_BytesObject_layout` functions). It also
    overrides `call()`: when a WASM trap occurs and a panic message was
    recorded, it re-raises it as a proper `SPyError` with location info.
    It provides `read_str()` / `read_bytes()` to decode SPy objects from
    linear memory.

## Done once vs done per SPyVM

This is the crucial lifecycle distinction:

```
   done ONCE per process              done once PER SPyVM
 ─────────────────────────       ──────────────────────────────

  libspy.wasm (on disk)
       │
       │ compile
       ▼                            instantiate
  LLMOD: LLWasmModule ──────┬────────────────►  vm1.ll: LLSPyInstance
  (stateless, compiled      │                   ├─ own wt.Store
   code, shared)            │                   ├─ own linear memory
                            │                   └─ own LibSPyHost
                            │
                            └────────────────►  vm2.ll: LLSPyInstance
                                                ├─ own wt.Store
                                                ├─ own linear memory
                                                └─ own LibSPyHost
```

- **Once per process**: loading and compiling the WASM bytes
  (`LLWasmModule` / `LLMOD`), and the wasmtime `Engine`.

- **Once per `SPyVM`**: the instantiation (`LLSPyInstance`), which creates
  a fresh store, a fresh linear memory and runs `_initialize`. Two VMs in
  the same process are therefore fully isolated: a pointer obtained from
  one VM's memory is meaningless in the other.

The connection with the object model: `W_Str` (see `spy/vm/str.py`) is
little more than a `spy_StrObject *` — an integer offset into `vm.ll`'s
linear memory. Creating an interp-level string means calling the WASM
function `spy_str_alloc` and writing the UTF-8 bytes into linear memory:

```python
def ll_str_new(ll: LLSPyInstance, s: str) -> int:
    utf8 = s.encode("utf-8")
    length = len(utf8)
    ptr = ll.call("spy_str_alloc", length)
    utf8_ptr = ll.mem.read_i32(ptr + ll.str_layout.utf8_offset)
    ll.mem.write(utf8_ptr, utf8)
    return ptr
```

## How the test suite uses llwasm

The C backend tests compile each test module to WASM (target `wasi`, kind
`lib`) and call its functions from Python through
`spy.tests.wasm_wrapper.WasmModuleWrapper`. The compiled module is linked
with `--whole-archive libspy.a`, i.e. it *contains its own copy of libspy*,
and is loaded into its own `LLSPyInstance`.

This means that during a C-backend test there are **two unrelated WASM
instances**, each with its own linear memory:

```
  SPyVM ──── vm.ll ────────────►  LLSPyInstance A: libspy.wasm
                                  (memory A: interp-level strings, etc.)

  WasmModuleWrapper ── .ll ────►  LLSPyInstance B: test_mod.wasm
                                  (memory B: statically-linked libspy +
                                   compiled test code)
```

`WasmFuncWrapper` converts arguments and return values at the boundary of
instance B: scalars pass through, strings are allocated into B's memory
with `ll_str_new`, and struct return values (flattened by wasmtime thanks
to the multivalue ABI) are reconstructed by reading B's memory.

`spy/tests/test_llwasm.py` tests both backends: the same tests run once
under plain CPython (wasmtime backend) and once inside Pyodide-on-node
(emscripten backend), via `pytest-pyodide`.

## Out-of-tree builtin modules

**Out-of-tree builtin modules** (see `examples/out-of-tree/`) are builtin
VM modules which live outside the SPy source tree and typically wrap an
existing C library. In interpreted mode their compiled C code must be
loaded into the VM and must be able to call libspy (e.g. `spy_gc_alloc`)
and to exchange pointers with it — i.e. it must share libspy's linear
memory.

Crucially, this does **not** mean instantiating multiple WASM modules into
a shared store. `llwasm` is unchanged: there is still exactly one
`LLWasmModule` and one `LLWasmInstance` per VM. Instead, the sharing is
achieved at *build time* by statically linking everything into a single
WASM module:

```
   libspy.a   +   mymod.a   +   othermod.a
        │            │              │
        └────────────┴──────────────┘
                     │  zig cc --whole-archive, link as one reactor
                     ▼
              libspy+mymod+othermod.wasm   (one bundle)
                     │
                     ▼
         vm.ll: LLSPyInstance  (one store, one linear memory)
```

This is symmetric with native compiled mode, where `spy -c` links
`libspy.a` and the out-of-tree `.a` together into the executable. An
out-of-tree module author writes ordinary C that `#include`s libspy
headers and calls libspy functions directly; the same `.a` is consumed
by both the native linker and the WASM bundler.

### The bundle build

`spy/build/wasm_bundle.py` does the linking:

  - `link_bundle(archives, exports, *, out)` invokes `zig cc` with
    `--target=wasm32-wasi-musl -mexec-model=reactor`, wrapping *every*
    archive in `--whole-archive` (symbols reachable only via WASM exports
    would otherwise be discarded — the same reason today's `libspy.wasm`
    build already wraps `libspy.a`), and emitting one `--export=` per
    requested symbol. The result is a single self-contained reactor
    module: one `_initialize`, one `memory`, one set of exports.

  - `get_or_build_bundle(archives, exports)` wraps `link_bundle` with a
    content-addressed cache under `<spy-root>/build/wasm-bundles/<hash>/`.
    The cache key hashes the content of each input `.a`, the sorted export
    list, and the `zig cc` version. Linking a bundle costs ~1–2s, paid
    once per (set-of-modules, libspy-version) pair; the cache lives
    project-local so `git clean -fdx` clears it along with other build
    artefacts.

### Wiring into the VM

`spy/libspy/get_LLMOD(extra_archives, extra_exports)` is the glue: with no
extra archives it returns the prebuilt global `LLMOD` (no build step, no
regression for VMs that don't use out-of-tree modules); otherwise it
prepends `libspy.a`, calls `get_or_build_bundle`, and returns an
`LLWasmModule` for the resulting bundle.

The chain that feeds it, starting from the user:

  - **`spy.toml`** (read by `spy/cli/spy_toml.py`) declares
    `extra-vm-modules = [...]`, a list of paths to out-of-tree module
    packages. The CLI's `--extra-vm-module` flag appends to this list.

  - **`SPyVM(extra_vm_modules=[...])`** imports each package (via
    `_import_extra_vm_module`), expecting a `MODULE` attribute
    (a `ModuleRegistry`) and an optional `build_info` callable.

  - **`build_info(target, build_type) -> BuildInfo`** (see
    `spy/build/build_info.py`) is how a module reports its compiled
    artefacts. The VM calls each module's `build_info("wasi", "debug")`,
    collects the `.archives`, and passes them to `get_LLMOD`. The same
    `BuildInfo` (with `target="native"`) is consumed by the C backend when
    compiling to a native executable.

So the same out-of-tree module package drives both modes: in interpreted
mode its `wasi` archive is bundled into `vm.ll`, and in compiled mode its
`native` archive is linked into the executable.

### Pyodide / emscripten

The bundling described above currently targets `wasi` (the wasmtime
backend). The emscripten path — bundling `.a` files with `emcc` into a
`.mjs` for use under Pyodide — follows the same design but is not yet
wired up; the `llwasm` emscripten backend itself needs no changes, since
loading a bundled `.mjs` is identical to loading today's `libspy.mjs`.
