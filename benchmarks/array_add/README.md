# Minimal benchmark simple array

Example of output of `make`:

```
python bench_numpy.py
./build/bench
spy add: 0.166543 s
spy add inplace: 0.0124178 s
spy empty: 0.105744 s
spy zeros: 0.131674 s
```
The runtime is highly dominated by allocations.
