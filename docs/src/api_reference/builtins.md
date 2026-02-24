title: Built-in Functions
---

## Implemented CPython-Like Built-ins 

The following built-in functions work similarly to their equivalents in CPython; see the specific functions below for notes

### `dict()`
The syntax `dict[keytype, valuetype]()` can be used to create a new empty dict of the given types; unlike CPython, this does not (currently) accept an Iterable to create a new dict from.

### `float()`

### `getattr()`

### `hash()`
Currently implented for types: `i8`,`i32`, `u8`, `bool`, `str`.

By default, instances of SPy classes are not hashable are not hashable. Users can implement the `__hash__` function to permit hashing.

### `int()`

### `len()`

### `list[type]()`
The syntax `list[type]()` can be used to create a new empty list of the given type; unlike CPython, this does not (currently) accept an Iterable to create a new list from.

### `print()`

### `range()`

### `repr()`

### setattr()

### slice()

### str()

## Not-Implemented CPython-Like Built-ins 

abs(), aiter(), all(), anext(), any(), ascii(), bin(), bool(), breakpoint(), bytearray(), bytes(), callable(), chr(), classmethod(), compile(), complex(), delattr(), dir(), divmod(), enumerate(), eval(), exec(), filter(), format(), frozenset(), globals(), hasattr(), help(), hex(), id(), input(), isinstance(), issubclass(), iter(), locals(), map(), max(), memoryview(), min(), next(), object(), oct(), open(), ord(), pow(), property(), reversed(), round(), set(), sorted(), staticmethod(), sum(), super(), tuple(), type(), vars(), zip(), __import__()

## Functions Unique to SPy