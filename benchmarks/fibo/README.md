# A tiny recursive Fibonacci benchmark: CPython, Julia, Codon, SPy

:::{warning}
This benchmark uses naive recursive Fibonacci — a classic microbenchmark that is almost
entirely a measure of **function call overhead and compiler recursion optimisation**. It
has essentially nothing to do with real scientific or numerical code.
:::

## Results

| Implementation        | Time (s) | Speedup vs CPython |
| --------------------- | -------- | ------------------ |
| CPython 3.x           | 15.2     | 1x                 |
| PyPy 3.11             | 1.85     | ~8x                |
| Julia -O3             | 0.55     | ~28x               |
| Codon --release       | 0.28     | ~54x               |
| SPy --release (gcc)   | 0.23     | ~66x               |
| SPy --release (clang) | 0.34     | ~45x               |

## The surprising result: why is Julia 2x slower than Codon/SPy?

Julia is a compiled language with a mature LLVM backend and `-O3` explicitly enabled, so
one might expect it to match Codon and SPy. It does not, and the reason is instructive.

Julia compiles functions on first call via a JIT (Just-In-Time) compiler. Even though
Julia's LLVM backend is the same technology as clang's, a JIT operates under a hard
constraint: **compilation time is paid at runtime**. Julia's LLVM pipeline is therefore
deliberately tuned to be conservative — it limits inlining budgets and the depth of
interprocedural optimisation passes in order to keep latency acceptable.

Codon and SPy, by contrast, invoke the compiler **ahead-of-time (AOT)**: `codon build`
and `spy build --release` produce a native binary before any timing begins. With no
latency budget to respect, the AOT pipeline can apply much heavier optimisations.
