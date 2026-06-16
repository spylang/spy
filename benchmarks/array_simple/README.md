# Minimal benchmark simple array

Example of output of `make`:

```
python bench_numpy.py
numpy add: 0.081 s
numpy add inplace: 0.017 s
numpy empty: 0.000 s
numpy zeros: 0.043 s
spy build --release bench.spy
[release] build/bench
./build/bench
spy add: 0.0649705 s
spy add inplace: 0.0118649 s
spy empty: 0.00156045 s
spy zeros: 0.0392554 s
```

Before usage of `GC_MALLOC_ATOMIC`, the runtime was highly dominated by allocations.

```
./build/bench
spy add: 0.166543 s
spy add inplace: 0.0124178 s
spy empty: 0.105744 s
spy zeros: 0.131674 s
```
