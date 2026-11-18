title: Differences from CPython
---

/// warning
This page is incomplete.

It serves as a place where document the differences that we find and/or introduce while
we develop SPy.  The fact that something is not mentioned here does not necessarily mean
that it works the same as on CPython.
///

## `range` equality

In CPython, two `range` objects are considered equal if they represent the same sequence
of numbers. E.g.:

```
>>> range(0, 5, 2) == range(0, 6, 2)
True
```

In SPy, they are equal if their `.start`, `.stop` and `.step` fields are equal.

This is a design decision to avoid weird suprises when using `range` objects in blue
functions.  Blue functions are memoized: if we pass two objects which compare equal but
have visible differences, you could get unexpected results.  For example:

```python
@blue
def get_stop(r):
    return r.stop

def main() -> None:
    print(get_stop(range(0, 5, 2)))
    print(get_stop(range(0, 6, 2)))
```

This correctly prints `5 6`. If we used CPython-like equality, the second call would
return the cached result and it would print `5 5`, which is arguably very surprising.

Note that this problem already exists in CPython if you use e.g. `range` as a dict
key. This peculiar behavior of `range.__eq__` probably dates back to the
Python2-to-Python3 transition.
