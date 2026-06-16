from time import time


def fib(n):
    return n if n < 2 else fib(n - 1) + fib(n - 2)


t0 = time()
ans = fib(40)
t1 = time()
assert ans == 102334155
print(f"Computed fib(40) = {ans}")
print(f"# in {t1 - t0:.3f} seconds.")
