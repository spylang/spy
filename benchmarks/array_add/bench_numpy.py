import numpy as np

from time import time

size = 1000000

arr = np.ones(size)

t_start = time()
for _ in range(100):
    res = arr + arr
print(f"numpy: {time() - t_start:.3f} s")

t_start = time()
for _ in range(100):
    np.add(arr, arr, out=arr)
print(f"numpy (inplace): {time() - t_start:.3f} s")
