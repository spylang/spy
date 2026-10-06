# StrBuilder experiments

Benchmark of several designs for building a `str` piece by piece, with Boehm GC
(the only supported GC for now).

    spy build -x --release benchmarks/strbuilder/bench.spy

## Implementations

| file | design |
|---|---|
| `strbuilder_chunked.spy` | chunk list (linked, newest first) behind a `gc_ptr[State]`. Mutating `sb.append(x)`, sealed by `build()`. |
| `strbuilder_chunked_list.spy` | same, but the closed chunks live in a `list[Piece]` |
| `strbuilder_fn.spy` | chunk list inside a plain value: `sb = sb.append(x)`, stale copies detected through the `StrObject` header |
| `strbuilder_realloc.spy` | one growable `StrObject`, grown with `StrObject.realloc` (CPython style), doubling |
| `strbuilder_unsafe_fixed.spy` | fixed capacity, no checks, 16 byte value: for code which knows the size |

All chunks are `StrObject`s: if nothing overflows the first one, `build()` is
a length update plus a cast (no copy). `bench.spy` has one column per design,
plus `chunked-exact`: the same builder as `chunked`, created with the exact
final size (`unsafe` has it too).

## Machine

Results below were measured on 2026-10-06, git `eb82f61c` plus the uncommitted
changes of this work, on AC power, no CPU pinning, with the usual desktop
applications running.

- Intel Core i7-8550U (Kaby Lake R laptop CPU): 4 cores / 8 threads, 1.8 GHz
  base, 4.0 GHz turbo, L2 1 MiB, L3 8 MiB; cpufreq governor `powersave`
  (intel_pstate, i.e. dynamic frequency)
- 15 GiB RAM, Ubuntu 24.04, Linux 6.8.0, x86_64
- gcc 13.3.0, `-O3 -flto`, `spy build --release`; Boehm GC 8.2.6 (system
  `libgc`), no tuning of the heap

## Results

Microseconds, median of 3 runs, lower is better. The 1 MB rows vary by up to
1.6x between runs (e.g. `csv-1MB` chunked: 979 / 1077 / 1658), the others by
less than 10%. Only large, repeatable differences should be trusted.

| row | realloc | chunked | chunked-exact | list | fn | unsafe |
|---|---|---|---|---|---|---|
| 1 MB from 2 B appends | 2377 | 2476 | 1941 | 2124 | 2654 | 1721 |
| 1 MB from 16 B appends | 347 | 280 | 172 | 283 | 302 | 188 |
| 1 MB from 128 B appends | 168 | 120 | 67 | 193 | 169 | 111 |
| 1 MB from 1 KB appends | 199 | 104 | 83 | 226 | 172 | 82 |
| 1 MB from 4 KB appends | 214 | 48 | 52 | 120 | 113 | 119 |
| json-1KB (321 appends) | 1.4 | 1.4 | 1.1 | 1.4 | 1.6 | 0.9 |
| json-64KB (19921 appends) | 84 | 84 | 70 | 75 | 100 | 64 |
| json-1MB (303761 appends) | 1420 | 1885 | 1189 | 1373 | 1808 | 1076 |
| csv-1KB (228 appends) | 0.9 | 1.1 | 0.9 | 0.9 | 1.1 | 0.7 |
| csv-64KB (13418 appends) | 62 | 60 | 50 | 56 | 71 | 46 |
| csv-1MB (204358 appends) | 1559 | 1077 | 868 | 1559 | 1747 | 897 |
| repr of a 100 items list | 11 | 11 | - | 11 | 11 | - |

The `repr` benchmarks of `list[int]` / `list[float]` (sections 3 and 4 of
`bench.spy`) tie for all builders (within 3%): the time is spent formatting a
temporary `str` per item.

## What we found

- **No design wins everywhere.** For documents up to 64 KB, `realloc` and
  `chunked` are the same speed. At 1 MB the order depends on the run, so it is
  inconclusive. `chunked` and `list` win clearly (2-4x) only for **large
  appends** (1 KB and more): a big string is linked as a piece without being
  copied, while `realloc` has to copy it. `fn` is the slowest design for
  small appends.
- **Growth factor of `realloc`:** with Boehm most growths copy, so a geometric
  factor matters. Doubling is the best (x1.5 and x1.25, which CPython uses
  because of glibc `realloc`, are worse); `bench.spy` uses doubling.
  Comparisons done with x1.25 made `realloc` look 2-3x slower than the chunk
  list: they were misleading.
- **Exact capacity pays off:** `chunked-exact` is 1.2-1.8x faster than
  `chunked` (no growth, no consolidation copy), more than any choice of
  growth strategy. A pre-pass is worth it only if it is cheap: for
  `list[int]` it ties with an estimate, for `list[float]` it is 2x slower
  because it has to format every item twice. Overestimating costs nothing,
  `build()` drops the slack.
- **The checks of the safe builder cost about 10%:** `chunked-exact` vs
  `unsafe`, which has the same capacity but no state and no checks.
- **Inlining matters more than the design.** The by-value builder (`fn`) was
  4x slower on small appends until `append` was `@force_inline`: a 32 byte
  struct is passed and returned through memory, which stalls store
  forwarding. Every `append` is now an inlined fast path plus a separate slow
  path. Even so, `fn` stays 10-25% slower than `chunked` on the JSON/CSV
  rows. We did not investigate why.
- **Linked list vs `list[Piece]`: mixed.** `list` is 10-25% faster on the
  64 KB and 1 MB JSON rows, and 2x slower on 128 B - 1 KB appends. The list
  needs three allocations on the first growth, and there are only about
  log2(size) chunks anyway. Walking the linked list backwards in `build()`
  costs nothing measurable.
- **Parameters of `chunked` are on a plateau.** New chunk size = total so
  far + size of the append (growth x1). Growing faster (x2, x4) was 25-50%
  worse. Chunk rounding (16-1024), a minimum chunk size and the initial
  capacity (16-1024) made no measurable difference. Adopting big appends as
  pieces must stay enabled for appends around 8 KB (2-3x slower without it);
  the threshold 4096 is fine. (The sweep script is not kept.)
- **Benchmarking caveat:** the same code compiled with different constants
  varies by +-20% per row because of code layout. To compare variants,
  divide the time with the default capacity by the time with the exact
  capacity of the same executable, and interleave the runs.

## The `gc_realloc.patch` patch

`bench.spy` does not build on a plain checkout: `strbuilder_realloc.spy` needs
a few additions to SPy and libspy, which are in `benchmarks/gc_realloc.patch`.
From the root of the repo:

    git apply benchmarks/gc_realloc.patch
    make -C spy/libspy TARGET=native BUILD_TYPE=release   # and debug, and
    make -C spy/libspy TARGET=wasi BUILD_TYPE=debug OUTPUT_KIND=testlib

(libspy has to be rebuilt, because the patch touches `str.c` and `unsafe.c`.)
Without the patch only the `realloc` column is lost: remove the
`strbuilder_realloc` import and its uses from `bench.spy`.

Why it is needed:

- **A realloc primitive.** SPy had `gc_alloc` but no way to resize a buffer.
  The patch adds `unsafe.gc_realloc[T](p, n)`, backed by `GC_REALLOC` in
  compiled code (`unsafe.h`, `mem.py`, `unsafe.c`).
- **`StrObject.realloc`**, and not just `gc_realloc[StrObject]`: a
  `StrObject` header and its bytes are one allocation, so the size is
  `sizeof(header) + n`, not `n * sizeof(StrObject)`, and `utf8` points inside
  the block, so it has to be fixed up after the block moves. This is what
  `ReallocStrBuilder` calls (`str.h`, `str.c`, `ptr.py`, `stdlib/_str.spy`).
- **Strings must be allocated by the GC of the program.** `libspy.a` is
  always built with `SPY_GC_NONE`, so `spy_str_alloc` was plain `malloc`: such
  a block can't be passed to `GC_REALLOC`, and it was never collected. The
  patch makes `StrObject.alloc` in compiled code use the program's GC
  (`spy_str_gc_alloc` in `str.h`, inline so that it follows `-DSPY_GC_BDWGC`),
  with `GC_MALLOC_ATOMIC`, since a `StrObject` has no pointers outside its own
  block.

Side effect: **every `str` allocated by `StrObject.alloc` in compiled code is
now garbage collected**, and the test suite has not been run with the patch.

Known bug, not fixed by the patch: `libspy.a` is always compiled with
`SPY_GC_NONE`, so everything it allocates itself (`str`s from `i32.__str__`,
`bytes`, raw buffers) is `malloc`ed and never freed, even in Boehm builds. The
fix is to allocate through the GC of the program being compiled, not the one
libspy was built with.

## Not tried

- Threads, and the `__fastformat__` protocol, where every value writes
  directly into the builder. The list repr numbers can't tell the builders
  apart until the temporary `str` per item goes away.
