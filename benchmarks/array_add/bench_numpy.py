import numpy as np

from time import time

size = 1000000

arr = np.ones(size)

t_start = time()
for _ in range(100):
    res = arr + arr
print(f"numpy add: {time() - t_start:.3f} s")

t_start = time()
for _ in range(100):
    np.add(arr, arr, out=arr)
print(f"numpy add inplace: {time() - t_start:.3f} s")

t_start = time()
for _ in range(100):
    res = np.empty(size)
print(f"numpy empty: {time() - t_start:.3f} s")

t_start = time()
for _ in range(100):
    res = np.zeros(size)
print(f"numpy zeros: {time() - t_start:.3f} s")
