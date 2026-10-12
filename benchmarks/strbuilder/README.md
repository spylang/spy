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
| `stdlib/strbuilder.spy` | the builders we actually ship: `StrBuilder` (growable, checked) and `UnsafeFixedStrBuilder` (fixed, unchecked) |

All chunks are `StrObject`s: if nothing overflows the first one, `build()` is
a length update plus a cast (no copy). `bench.spy` has one column per design,
plus `chunked-exact`: the same builder as `chunked`, created with the exact
final size (`unsafe` has it too).

The last three columns are the stdlib builders: `std` is `StrBuilder` with the
same capacity as `chunked`, `std-exact` is `StrBuilder` with the exact final
size, and `std-unsafe` is `UnsafeFixedStrBuilder` with the exact size. They are
the same designs as `chunked`, `chunked-exact` and `unsafe`, so they are the
ones to compare against.

## Machine

Results below were measured on 2026-10-12, git `0bf57588` with
`benchmarks/gc_realloc.patch` applied (so that the `realloc` column is a real
realloc), on AC power, no CPU pinning, with the usual desktop applications
running. All the builders run in the same process: see "GC and one process"
below before trusting the `std` rows between 128 B and 4 KB.

- Intel Core i7-8550U (Kaby Lake R laptop CPU): 4 cores / 8 threads, 1.8 GHz
  base, 4.0 GHz turbo, L2 1 MiB, L3 8 MiB; cpufreq governor `powersave`
  (intel_pstate, i.e. dynamic frequency)
- 15 GiB RAM, Ubuntu 24.04, Linux 6.8.0, x86_64
- gcc 13.3.0, `-O3 -flto`, `spy build --release`; Boehm GC 8.2.6 (system
  `libgc`), no tuning of the heap

## Results

Microseconds, median of 7 runs of the same executable, lower is better. The 1 MB
rows vary a lot between runs (e.g. `csv-1MB` chunked: 1037 / 1093 / 1625; `std`:
1559 / 1657 / 1833), the others by less than 10%. Only large, repeatable
differences should be trusted.

| row | realloc | chunked | chunked-exact | list | fn | unsafe | std | std-exact | std-unsafe |
|---|---|---|---|---|---|---|---|---|---|
| 1 MB from 2 B appends | 2001 | 2450 | 2042 | 2416 | 2736 | 1820 | 2204 | 2228 | 1746 |
| 1 MB from 16 B appends | 316 | 261 | 190 | 266 | 315 | 154 | 268 | 190 | 174 |
| 1 MB from 128 B appends | 221 | 129 | 91 | 150 | 164 | 93 | 170 | 93 | 97 |
| 1 MB from 1 KB appends | 220 | 181 | 72 | 163 | 177 | 85 | 197 | 86 | 69 |
| 1 MB from 4 KB appends | 245 | 56 | 94 | 75 | 163 | 158 | 113 | 88 | 156 |
| json-1KB (321 appends) | 1.4 | 1.6 | 1.1 | 1.6 | 1.9 | 1.4 | 1.6 | 1.4 | 1.1 |
| json-64KB (19921 appends) | 74 | 87 | 69 | 88 | 97 | 76 | 81 | 77 | 66 |
| json-1MB (303761 appends) | 1319 | 1507 | 1196 | 1502 | 2020 | 1299 | 1884 | 1370 | 1148 |
| csv-1KB (228 appends) | 0.9 | 1.1 | 0.7 | 1.1 | 1.1 | 0.9 | 0.9 | 0.9 | 0.7 |
| csv-64KB (13418 appends) | 56 | 64 | 50 | 66 | 71 | 54 | 62 | 56 | 46 |
| csv-1MB (204358 appends) | 1093 | 1105 | 874 | 1602 | 1724 | 936 | 1657 | 992 | 790 |
| repr of a 100 items list | 11 | 10 | - | 11 | 11 | - | 11 | - | - |

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
- **The stdlib builders match the best designs.** `std-unsafe`
  (`UnsafeFixedStrBuilder`) ties with `unsafe` or beats it (0.8-1.1x). `std-exact`
  is 0.9-1.3x of `chunked-exact` (about 1.1x on the JSON/CSV rows): the cost is the
  bounds check and the extra work of the safe `append`. `std` is within 10% of
  `chunked` on most rows, but the 128 B - 4 KB rows of the table look 1.3-2x slower:
  that is a measurement artefact, see "GC and one process" below. Big appends are
  adopted by the stdlib builder too (the 4 KB row was 2x slower without it).
- **Benchmarking caveat:** the same code compiled with different constants
  varies by +-20% per row because of code layout. To compare variants,
  divide the time with the default capacity by the time with the exact
  capacity of the same executable, and interleave the runs.

## GC and one process

`bench.spy` runs all the builders one after the other, in the same process. With
`gc_realloc.patch` applied every `StrObject` is allocated by Boehm GC, and a
collection is triggered by the garbage of whoever ran before: its cost is charged
to the builder which happens to run next. So the order of the columns biases the
results, especially for rows which allocate and drop 1 MB at every run (the 128 B,
1 KB and 4 KB rows). We saw it in three ways:

- In the table above `std` is 1.3-2x slower than `chunked` on the 128 B - 4 KB
  rows. A plausible reason is that `std` is the first of the stdlib columns, so it
  runs right after `unsafe`; we did not prove it.
- The same two builders in the same loop: with `chunked` first the `append` phase
  at 1 KB took 41 us (`chunked`) and 46 us (`std`); with `std` first it took 120 us
  (`std`) and 46 us (`chunked`). Only the order changed.
- Counting instructions (`valgrind --tool=callgrind`, 128 B appends): `chunked`
  72.5 M, `std` 70.6 M, and the same 48.5 M in `memcpy`. They do the same work.

Without the patch nothing is freed, so there are no collections, but then every
run touches fresh pages and page faults dominate: the 4 KB row of `chunked`
takes about 446 us instead of about 43 us, and `realloc` can't be built.

The fair comparison is one executable per builder, with the builders run
alternately. Results for the 1 MB from equal appends rows, with the patch applied,
3000 builds per run, 8 alternating runs, user time per build (us):

| append size | chunked (min / mean) | std (min / mean) | std / chunked (min / mean) |
|---|---|---|---|
| 128 B | 130 / 151 | 127 / 149 | 0.97 / 0.99 |
| 1 KB | 113 / 133 | 107 / 122 | 0.94 / 0.92 |
| 4 KB | 40 / 48 | 47 / 50 | 1.17 / 1.03 |

So `std` and `chunked` are the same speed (the 4 KB row is 3-17% slower, the only
one which might be real). The script used for this is not kept: it is
`bench.spy` reduced to one builder, selected by a constant at compile time.
We did not repeat this for the other rows. The 1 KB and 64 KB JSON/CSV rows and the
`repr` rows agree with `chunked` within noise; the 1 MB JSON/CSV rows (`std` 1.25x
and 1.5x slower) are noisy and might be affected too, we don't know.

To get reliable numbers from `bench.spy` itself, run one builder per process or
force a collection (`GC_gcollect`) between the builders: neither is done yet.

## Results (Apple M1 Pro, macOS)

Measured on 2026-10-12, git `0bf57588`, on AC power, no CPU pinning, with the
usual desktop applications running.

- Apple M1 Pro, 32 GiB RAM, macOS 15.7.7, arm64
- Apple clang 17.0.0, `spy build --release`; Boehm GC 8.2.12 (homebrew
  `bdw-gc`), no tuning of the heap

The `realloc` column is missing: `gc_realloc.patch` was not applied, so the
benchmark was a copy of `bench.spy` with the `realloc` import and uses
removed. Two macOS-specific notes:

- `spy build --release` needs a Boehm GC; with no `bdw-gc` in the conda env it
  falls back to homebrew only if `CONDA_PREFIX` is unset, so the build was run
  as `env -u CONDA_PREFIX spy build --release bench_norealloc.spy`
  (`spy/build/config.py`, `add_libgc`).
- `--static` is not an option on macOS: the vendored libgc build uses
  `zig cc --target=native-native-musl`, which is Linux-only.

Microseconds, best of 5 runs (more for the small rows), lower is better. The
1 KB rows (`json-1KB`, `csv-1KB`, the 10-items repr) are at or below the
resolution of `time()` here, so all the builders tie at 0.0-0.9 us.

| row | chunked | chunked-exact | list | fn | unsafe | std | std-exact | std-unsafe |
|---|---|---|---|---|---|---|---|---|
| 1 MB from 2 B appends | 1259 | 1159 | 1321 | 1401 | 1118 | 1221 | 1088 | 1083 |
| 1 MB from 16 B appends | 365 | 279 | 378 | 412 | 277 | 384 | 278 | 270 |
| 1 MB from 128 B appends | 210 | 109 | 195 | 210 | 97 | 217 | 109 | 114 |
| 1 MB from 1 KB appends | 180 | 98 | 176 | 182 | 87 | 172 | 95 | 90 |
| 1 MB from 4 KB appends | 127 | 103 | 118 | 122 | 113 | 117 | 113 | 101 |
| json-64KB (19921 appends) | 76 | 69 | 75 | 77 | 64 | 77 | 69 | 63 |
| json-1MB (303761 appends) | 1224 | 1079 | 1148 | 1189 | 985 | 1178 | 1076 | 987 |
| csv-64KB (13418 appends) | 58 | 52 | 58 | 58 | 47 | 59 | 52 | 48 |
| csv-1MB (204358 appends) | 945 | 831 | 918 | 958 | 775 | 955 | 790 | 736 |
| repr of a 100 items list | 5 | - | 5 | 5 | - | 5 | - | - |
| int n=1000 exact | 73 | - | 72 | 73 | 72 | 73 | - | 71 |
| float n=1000 exact | 191 | - | 189 | 195 | 194 | 195 | - | 195 |

What changes with respect to the x86/Linux machine:

- **The qualitative picture is the same.** Exact capacity beats the default
  one (`chunked-exact` vs `chunked`: 1.1-1.9x), `unsafe` / `std-unsafe` are
  the fastest, and the stdlib builders are within a few % of the
  hand-rolled designs they mirror (`std` vs `chunked`, `std-exact` vs
  `chunked-exact`, `std-unsafe` vs `unsafe`).
- **The M1 Pro is 1.5-2x faster** than the i7-8550U on the same rows (e.g.
  2 B appends: 1259 vs 2476 us for `chunked`).
- **`fn` is much closer to `chunked` here**: nearly tied on the JSON/CSV rows
  (e.g. json-1MB 1189 vs 1224 us), where on x86 it stayed 10-25% slower even
  after `@force_inline`. The by-value struct passing penalty is smaller on
  this chip.
- **`list` no longer loses on mid-size appends**: on 128 B - 1 KB appends it
  ties with `chunked` (195/176 vs 210/180 us), where on x86 it was up to 2x
  slower.

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
