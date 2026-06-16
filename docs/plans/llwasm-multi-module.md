# Loading out-of-tree builtin modules into `vm.ll`

## Goal

A SPy `SPyVM` should be able to load **out-of-tree builtin modules**:
self-contained C libraries (typically wrappers around an existing
third-party library — see `examples/out-of-tree/`) that live outside
the SPy source tree but become first-class members of the VM at
runtime, alongside `libspy` itself.

In compiled mode (`spy -c`) this already works the obvious way: the
out-of-tree module ships a static archive `mymod.a`, and the C
compiler/linker combines it with `libspy.a` and the user's code into
a native executable.

In **interpreted mode** the same VM also needs the out-of-tree
module's compiled C code, but today `vm.ll` only knows how to load
**one** WASM file (`libspy.wasm`). This document is the plan for
filling that gap.

---

## 1. The design in one paragraph

We do **not** add multi-module support to `llwasm`. Instead, we let
`wasm-ld` (via `zig cc`) do what it already does well: combine
multiple `.a` archives into a single `.wasm` reactor module, ahead
of time, with a cache keyed on the inputs. The out-of-tree module
ships a `.a` (built for `wasm32-wasi-musl`); when `vm.ll` is
constructed, SPy ensures a bundle `libspy+modA+modB.wasm` exists for
the requested set of modules — building it on demand and caching it
— and then loads that single bundle through the existing
`LLWasmInstance` machinery, unchanged. From `llwasm`'s point of view
nothing has changed: there's still exactly one module per VM.

---

## 2. Why static-link bundling, not runtime multi-module

The alternative — instantiating multiple `.wasm` modules into a
shared `wt.Store` and `wt.Memory`, with side modules declaring
`env.<libspy-symbol>` imports — is mechanically possible (a spike
confirmed it works). But it has consequences that don't survive
contact with real out-of-tree modules:

- **Headers stop being shareable.** A side module can't just
  `#include "spy/str.h"` and call `spy_str_alloc()`: in the
  multi-module world, calls into libspy must be declared as
  `WASM_IMPORT(spy_str_alloc)` on the side-module side. Either every
  out-of-tree module redeclares the parts of the libspy API it uses
  (boilerplate, drift hazard), or libspy headers grow a third
  compile mode (native / libspy-internal / side-module) that flips
  every prototype between `WASM_EXPORT`, plain, and `WASM_IMPORT`.
  Both options are bad.

- **Two build models for two targets.** With multi-module wasm,
  out-of-tree modules build differently for native (link `.a`,
  ordinary C) and wasm (build a side module with magic linker
  flags, `WASM_IMPORT` everything). Static-link bundling collapses
  these: the out-of-tree module produces a `.a` for both, and the
  *only* per-target difference lives in `spy/build/`.

- **No LTO across module boundaries.** Calls to `spy_str_alloc`
  from a side module become non-inlinable WASM imports. With static
  bundling and `-flto`, those calls inline as they do natively.

- **`--global-base` coordination.** Multi-module side modules have
  to be compiled with a hard-coded `--global-base=N` so their
  `.data` doesn't collide with libspy's. That's a magic number we'd
  have to either fix forever or negotiate at build time. Static
  bundling lets `wasm-ld` lay out memory.

What we give up by going static:

- **No runtime `dlopen`.** Every combination of (libspy + modules)
  has to be linked into a bundle ahead of use. For the actual use
  case — modules declared in `spy.toml` / chosen at VM construction
  time — this is a non-issue. It would matter only for scenarios
  like a hosted playground that loads arbitrary unseen modules at
  runtime, which is not on the roadmap.

- **Cold-start cost on first use of a new combination.** Linking
  libspy + a small side module with `zig cc` is on the order of
  1–2s. Hits once per (set-of-modules, libspy-version) pair, then
  cached.

The trade is worth it: out-of-tree module authors write ordinary C
that `#include`s libspy headers and works the same on native and on
wasm.

---

## 3. The build flow

### 3.1 What an out-of-tree module ships

A `.a` archive built for `wasm32-wasi-musl`, plus an explicit list
of symbols that should appear as WASM exports of the final bundle.
Concretely (for `examples/out-of-tree/`):

```
spyvm_qrcodegen/
├── build/
│   ├── wasi/qrcodegen.a          # zig cc --target=wasm32-wasi-musl
│   └── native/qrcodegen.a        # cc / zig cc native
├── src/qrcodegen_spy.c           # uses #include "spy.h"
└── spy.toml                      # declares exports + .a path
```

The `spy.toml` (or equivalent) entry tells SPy:
- where to find the `.a` for each target;
- which symbols to expose as bundle exports (e.g.
  `qrcodegen_encode_text`, `qrcodegen_get_size`, ...).

This is symmetric with how out-of-tree modules already work in the
native build: same `.a`, same exports list, just consumed by a
different linker invocation.

### 3.2 What SPy does with it

A new build step **link-bundle** that takes:

- `libspy.a` (the existing `spy/libspy/build/wasi/<build_type>/libspy.a`);
- one or more out-of-tree `.a` files;
- the union of all modules' export lists, plus libspy's standard
  reactor exports.

and runs:

```
zig cc --target=wasm32-wasi-musl -mexec-model=reactor \
    -Wl,--whole-archive libspy.a modA.a modB.a -Wl,--no-whole-archive \
    -Wl,--export=spy_str_alloc -Wl,--export=spy_gc_alloc ... \
    -Wl,--export=modA_foo -Wl,--export=modB_bar ... \
    -o libspy+modA+modB.wasm
```

`--whole-archive` for *every* archive, because libspy and out-of-tree
modules alike contain symbols that are reached only via WASM exports
(the linker's reachability analysis would discard them otherwise —
the same reason today's wasi+lib build already wraps `libspy.a` in
`--whole-archive`).

The result is a single self-contained reactor module: one
`_initialize`, one `memory`, one set of exports. No multi-module
runtime machinery anywhere.

### 3.3 Division of responsibility

**SPy is not the C build system for out-of-tree modules.** Each
out-of-tree module ships its own Makefile (or whatever it prefers)
that produces a `.a` for each target — exactly as
`examples/out-of-tree/vendor/qrcodegen/Makefile` does today.
`spy/build/config.py` and `spy/build/ninja.py` are tools for
compiling `.spy` programs and stay out of this entirely.

What SPy *does* need to provide:

1. **A documented, stable set of CFLAGS per target**, so an
   out-of-tree module's Makefile knows how to produce a `.a` that
   is compatible with libspy. These are essentially the C-compile
   flags already used in `spy/libspy/Makefile` (e.g. for `wasi`:
   `--target=wasm32-wasi-musl -mmultivalue -Xclang -target-abi
   -Xclang experimental-mv -mbulk-memory -fPIC -fvisibility=hidden`)
   plus `-I` pointing at libspy's public headers.

   This belongs as a small, easily-callable surface so module
   Makefiles can stay in sync without copy-pasting. Concretely a
   tiny helper script invokable from `make`:

   ```
   CFLAGS  := $(shell python -m spy.libspy.flags --cflags  --target=wasi)
   INCLUDE := $(shell python -m spy.libspy.flags --include)
   ```

   Output is plain space-separated flags. The script's logic is
   trivial — it just prints the known-good flags for each target —
   and its existence is the contract: anything an out-of-tree
   Makefile needs to pick up from libspy goes through this script.

2. **The link step** that combines `libspy.a` + N out-of-tree `.a`
   files into a single `.wasm` (or `.mjs`). This is a small Python
   helper, not a `BuildConfig`/`NinjaWriter` extension — there are
   no `.c` files, no compile step, no per-target matrix beyond what
   `spy/libspy/__init__.py` already knows. Roughly:

   ```python
   # spy/libspy/bundle.py
   def link_bundle(
       archives: list[py.path.local],   # libspy.a + each module's .a
       exports: list[str],
       *,
       target: BuildTarget,             # "wasi" | "emscripten"
       build_type: BuildType,
       out: py.path.local,
   ) -> None:
       # invoke zig cc / emcc with the right flags (§3.2)
       ...
   ```

   This shells out exactly the way `spy/libspy/Makefile`'s wasi
   rule already does — same compiler, same `--whole-archive`, same
   reactor model — just with extra `.a` inputs and extra
   `--export=` flags.

3. **The cache + lookup glue** in `spy/libspy/__init__.py`:
   `get_LLMOD(extra_archives, extra_exports) -> LLWasmModule`
   returns the cached prebuilt `libspy.wasm` if no extras are
   requested, and otherwise calls `link_bundle(...)` (cached on
   inputs).

No changes to `spy/llwasm/`. No changes to `spy/build/`. Everything
new lives under `spy/libspy/`, which is the right home: this is
all about *how libspy gets combined with extra C* before being
handed to llwasm as a `.wasm` blob.

### 3.4 Caching

The cache key is a content hash of:

- each input `.a` (libspy + each module);
- the sorted export list;
- the `BuildConfig` (target, build_type, opt_level, gc, ...);
- the toolchain version (`zig cc --version` output suffices).

Cache layout:

```
<spy-root>/build/wasm-bundles/
└── <hash>/
    ├── libspy+modA+modB.wasm
    └── manifest.json     # original input paths + exports, for debug
```

Project-local rather than `~/.cache/spy/` for two reasons: the
toolchain and libspy version are tightly coupled to the checkout,
and `git clean -fdx` already does the right thing for a stale cache.

A `--no-cache` flag (or `SPY_NO_BUNDLE_CACHE=1`) bypasses lookup,
useful while iterating on libspy itself.

### 3.5 When the bundle is built

At `SPyVM` construction time, after the registry of out-of-tree
modules is known. Concretely, `vm.ll` initialization grows from:

```python
self.ll = LLSPyInstance(LLMOD, ...)            # today
```

to roughly:

```python
extras   = collect_out_of_tree_archives(...)   # list[(name, .a, [exports])]
llmod    = spy.libspy.get_LLMOD(extras)        # cached build-or-load
self.ll  = LLSPyInstance(llmod, ...)
```

If `extras` is empty, `get_LLMOD` returns the same global
`LLWasmModule` it does today, with no build step at all — no
regression for VMs that don't use out-of-tree modules.

---

## 4. What out-of-tree module authors write

This is the experience we're optimizing for, and it's deliberately
identical to the native flow:

```c
// spyvm_qrcodegen/src/qrcodegen_spy.c
#include "spy.h"               // libspy public API
#include "qrcodegen.h"         // vendored third-party C lib

spy_Str * WASM_EXPORT(qrcodegen_encode_text)(spy_Str *text) {
    // ... call spy_str_alloc, spy_gc_alloc, etc. directly ...
    spy_Str *out = spy_str_alloc(n);
    // ...
    return out;
}
```

The author:

- `#include`s libspy headers normally; calls libspy functions
  normally;
- annotates entry points with `WASM_EXPORT` (already in `spy.h`,
  expands to `__attribute__((export_name(...)))` on wasi and to a
  no-op on native);
- ships the resulting object as a `.a`.

No `WASM_IMPORT` redeclarations of libspy. No magic linker flags.
No knowing or caring that `spy.h` exists in three flavors — it
doesn't.

---

## 5. The first test

Goal: confirm that two independently-compiled `.a` files can be
bundled into one `.wasm`, loaded by `llwasm` exactly as today, and
that functions defined in *either* archive are callable through
`ll.call`, sharing the same memory.

We use this minimal pair (no real libspy involvement — that comes
later):

```c
// part_a.c
#include <stdint.h>
int32_t shared_x = 100;
int32_t a_get_shared(void) { return shared_x; }
int32_t a_inc(void) { return ++shared_x; }
```

```c
// part_b.c
#include <stdint.h>
extern int32_t shared_x;       // resolved by part_a at link time
int32_t b_get_shared(void) { return shared_x; }
int32_t b_double(void) { shared_x *= 2; return shared_x; }
```

Test outline (in `spy/tests/test_llwasm.py`, alongside the existing
`TestLLWasm`):

```python
def test_bundle_multiple_archives(self):
    if self.llwasm_backend == "pyodide":
        pytest.skip("emscripten bundling not yet implemented")

    # Build each .c into its own .a (target=wasi).
    a_a = self.c_compile_archive(part_a_src, name="part_a")
    b_a = self.c_compile_archive(part_b_src, name="part_b")

    # Link them into a single .wasm, exporting both modules' funcs.
    bundle = self.wasm_link_bundle(
        archives=[a_a, b_a],
        exports=["a_get_shared", "a_inc", "b_get_shared", "b_double"],
    )

    from spy.llwasm import LLWasmInstance
    ll = LLWasmInstance.from_file(bundle)

    # Both archives' functions are reachable through one ll.call.
    assert ll.call("a_get_shared") == 100
    assert ll.call("b_get_shared") == 100      # same global as a's

    # State changes in one archive are visible from the other.
    assert ll.call("a_inc") == 101
    assert ll.call("b_double") == 202
    assert ll.call("a_get_shared") == 202
```

Two new test helpers are implied:

- `CTest.c_compile_archive(src, *, name) -> py.path.local`: invoke
  `zig cc` (with the same CFLAGS that
  `python -m spy.libspy.flags --cflags --target=wasi` prints) to
  produce a `.o`, then `zig ar rcs name.a name.o`. Returns the
  archive path. This is the test-suite's stand-in for
  out-of-tree-module Makefiles.
- `CTest.wasm_link_bundle(archives, *, exports) -> py.path.local`:
  thin wrapper around `spy.libspy.bundle.link_bundle` (§3.3). This
  is the one piece of new production code under test.

A second test exercises the libspy interaction: a single
out-of-tree-style archive that calls `spy_str_alloc`, bundled with
the real `libspy.a`, and verified end-to-end (allocate a string from
the side archive, read its contents back through `ll.mem`). This
catches the "side archive can `#include "spy.h"` and call libspy"
property that motivates the whole design.

A third, smaller test asserts the **caching**: building the same
bundle twice should reuse the cached `.wasm` (e.g. by checking that
the file's mtime is unchanged on second call), and modifying any
input `.a` should invalidate.

---

## 6. Step-by-step delivery

Each step is a separately-reviewable change.

1. **`spy.libspy.flags` helper.** A small CLI that prints the
   correct CFLAGS / include path / target triplet for a given
   target (`--target=wasi|emscripten|native|native-static`). The
   flags themselves are extracted from the values currently
   hard-coded in `spy/libspy/Makefile` so there is exactly one
   source of truth. Update `examples/out-of-tree/vendor/qrcodegen/Makefile`
   and `spy/libspy/Makefile` to use it, to prove the source-of-truth
   property in the same PR. No behavior change.

2. **`spy.libspy.bundle.link_bundle()`** — the link helper from
   §3.3. Plus the `c_compile_archive` test helper. Add the first
   test from §5 (two test archives bundled into one `.wasm`,
   exports from both reachable through one `ll.call`).

3. **Caching.** A small module (`spy/libspy/bundle_cache.py`) that
   hashes inputs, looks under `<spy-root>/build/wasm-bundles/`,
   builds on miss. Add the caching test from §5.

4. **`spy.libspy.get_LLMOD(extras)`.** Wire the cache into libspy's
   module loading: empty `extras` → today's behavior (untouched
   prebuilt path); non-empty → build/lookup the bundle. Add the
   "side archive calls `spy_str_alloc`" end-to-end test.

5. **Wire to `SPyVM` / `vm.ll` construction.** The VM's startup
   collects the registered out-of-tree modules' archives + exports,
   passes them to `get_LLMOD`. At this point the `examples/out-of-tree/`
   demo runs end-to-end in interpreted mode.

6. **Out-of-tree module manifest.** Decide the concrete
   `spy.toml` schema (or reuse what's already there): how a project
   declares an out-of-tree builtin module's archive paths and
   exports. Likely a small extension of what `examples/out-of-tree/`
   already uses.

Steps 1–4 are pure infrastructure and have no observable effect on
existing users; step 5 is where real behavior change lands.

---

## 7. Pyodide / emscripten

Same design, different toolchain. Out-of-tree modules ship a `.a`
built with `emcc` (`emcc -c -o foo.o`, `emar rcs foo.a foo.o`); the
bundle is produced by `emcc -sMAIN_MODULE=0 ... libspy.a modA.a -o
libspy+modA.mjs` (no `MAIN_MODULE`/`SIDE_MODULE` magic — it's just
ordinary static linking).

The interesting question is *who* runs `emcc`. On a developer
machine with emcc available, the same on-demand cache works. In a
deployed Pyodide environment (browser, no toolchain) we need
bundles to be built ahead of time during the project's `spy build`
or `spy package` step and shipped as static `.mjs` files. That's a
straightforward extension once §6 lands, and is not on the critical
path for the first interpreted-mode use cases.

The `llwasm` emscripten backend itself doesn't need any changes:
loading a bundled `.mjs` is identical to loading today's
`libspy.mjs`.

---

## 8. Out of scope

- **Runtime `dlopen` of unseen WASM modules.** If we ever want this
  (browser playground, plugin systems where the set of modules
  isn't known at VM construction time), we revisit. The static-link
  approach doesn't preclude it — it would coexist as a separate
  loading path in `vm.ll`.

- **Bundle size optimization.** A bundle that only uses 5% of
  libspy still pulls all of `libspy.a` in (because of
  `--whole-archive`). This is fine for now; if it becomes a
  problem, the lever is exporting only what the bundle actually
  needs and dropping `--whole-archive` for libspy specifically.

- **Cross-compilation from one host to a different bundle target.**
  The cache implicitly assumes the host's `zig cc` is the bundle's
  toolchain. Building wasi bundles from a Pyodide host (e.g. for a
  hosted SPy compiler) would need a separate code path.
