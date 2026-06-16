# SPy benchmarks

This directory collects performance benchmarks for SPy, comparing it against
CPython, PyPy, Julia, Codon, and NumPy depending on the benchmark.

> **Note — temporary home**
>
> This directory exists to gather benchmarks while SPy is maturing, when user
> code may break across commits. In the longer term, benchmarks will live in a
> dedicated repository that tracks SPy performance over time and presents
> results on a public website. The benchmarks here should eventually migrate
> there.

## Organisation

Each subdirectory is a self-contained benchmark with a `Makefile` that exposes
a set of standard targets:

| Target | Purpose |
|---|---|
| `make all` | Run every implementation available locally |
| `make check-ci` | Run the subset used in CI (all but CPython, which is too slow for CI) |
| `make test` | Run only the SPy implementation; output is compared against `expected_output/` |
| `make clean` | Remove build artefacts |

The `test` target is what the test suite (`test_spy_bench.py`) invokes. Its output
must be deterministic modulo timing lines, which are marked with a `#` prefix
(or an inline `#` sentinel) so the test framework can strip them before
comparison.

## Running the benchmarks

```bash
# Run a single benchmark (all implementations)
cd fibo && make all

# Run all benchmarks via pytest
pytest benchmarks/

# Run only SPy comparisons (fast, no extra deps)
pytest benchmarks/test_bench.py

# Run the full CI suite (requires Julia, Codon, PyPy)
pytest benchmarks/test_check_ci.py

# Regenerate expected output after an intentional SPy change
pytest benchmarks/test_bench.py --update-expected-output
```

## Dependencies

Beyond SPy itself, some benchmarks compare against:

- **NumPy** — installed with `uv pip install -e .[dev,bench]` or `pixi shell`
- **PyPy** — installed and managed via [uv](https://docs.astral.sh/uv/):

  ```bash
  uv python install pypy@3.11
  # then available as: uv python find pypy
  ```

- **Julia** — install from <https://julialang.org/downloads/> or via
  [juliaup](https://github.com/JuliaLang/juliaup):

  ```bash
  curl -fsSL https://install.julialang.org | sh
  ```

- **Codon** — install from <https://github.com/exaloop/codon>:

  ```bash
  /bin/bash -c "$(curl -fsSL https://exaloop.io/install.sh)"
  ```

## Relevant benchmark suites

Several external suites are good candidates for future SPy benchmarks:

- **[Julia microbenchmarks](https://github.com/JuliaLang/Microbenchmarks/)**
  ([results](https://julialang.github.io/Microbenchmarks/dev/benchmarks/)) —
  small, targeted kernels (`fib`, `pisum`, `parse_int`, ...). Useful for
  early-stage languages since they require very little stdlib support.

- **[Energy Languages](https://github.com/greensoftwarelab/Energy-Languages)**
  — based on the
  [Computer Language Benchmarks Game](https://benchmarksgame-team.pages.debian.net/benchmarksgame/index.html),
  but more modern and actively maintained. Covers both performance and energy
  consumption, which could be a differentiating angle for SPy. See also the
  [associated paper](https://greenlab.di.uminho.pt/wp-content/uploads/2017/10/sleFinal.pdf).

- **[nbabel](https://github.com/paugier/nbabel/)** — N-body simulation used
  to compare scientific computing languages. Particularly interesting because
  there are advanced, modern implementations in both Julia and Mojo, providing
  strong reference points for comparison.

- **[pyperformance](https://pyperformance.readthedocs.io/)** — the standard
  CPython benchmark suite, also used (with variations) by PyPy and GraalPy.
  Likely the most meaningful for positioning SPy relative to the Python
  ecosystem, though it requires broader stdlib coverage first.
