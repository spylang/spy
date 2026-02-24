title: CPython-Like Builtins
---

<style>
h3 {
  font-family: "Lucida Console", "Courier New", monospace;
}
</style>

## Implemented CPython-Like Built-ins 

The following built-in functions work similarly to their equivalents in CPython; see the specific functions below for notes

### __abs__`(object)`

:   Currently only implemented for int32's or objects convertable to int32's. The `__abs__` attribute is not currently supported.

### __dict__\[type\]()
:   The syntax `dict[keytype, valuetype]()` can be used to create a new empty dict of the given types; unlike CPython, this does not (currently) accept an Iterable to create a new dict from.

### __float__(object)

:   Converts `object` to a float if able

### __getattr__(obj, name: str)

:   `attr` must be blue

### __hash__(object)
:   Currently implented for types: `i8`,`i32`, `u8`, `bool`, `str`.

:   By default, instances of SPy classes are not hashable are not hashable. Users can implement the `__hash__` function to permit hashing.

### __int__(object)

:    Converts `object` to an int if able 

### __len__(object)

:   Return the length (the number of items) in a container

### __list__\[type\]()

:   The syntax `list[type]()` can be used to create a new empty list of the given type; unlike CPython, this does not (currently) accept an Iterable to create a new list from.

### __max__(x: i32, y: i32)

:   Currently only implemented for int32's or objects convertable to int32's.

### __max__(x: i32, y: i32)

:   Currently only implemented for int32's or objects convertable to int32's.

### __print__(obj)

:   The print function is currently not variadic, in the sense that it only accepts a single argument. The built-in types are special-cased, and SPy can always print blue objects by pre-computing their string representation

### __range__(stop)
### __range__(start, stop, step)

Creates an interable set of indices between `start` and `stop`, jumping over `step` indices between each.

### __repr__(object)

:   Returna string containing a printable representation of an object.

### __setattr__(object, name: str, value: obj)

:   `attr` must be blue

### __slice__(stop)
### __slice__(start, stop, step=None)

:   Return a slice object representing the items reached when iterating over range(start, stop, step). The start and step arguments default to None.

### __str__(object)

:   Returns a string version of the object. Selecting an encoding is not currently implemented.

## Not-Implemented CPython Built-ins 

:   aiter(), all(), anext(), any(), ascii(), bin(), bool(), breakpoint(), bytearray(), bytes(), callable(), chr(), classmethod(), compile(), complex(), delattr(), dir(), divmod(), enumerate(), eval(), exec(), filter(), format(), frozenset(), globals(), hasattr(), help(), hex(), id(), input(), isinstance(), issubclass(), iter(), locals(), map(), memoryview(), next(), object(), oct(), open(), ord(), pow(), property(), reversed(), round(), set(), sorted(), staticmethod(), sum(), super(), tuple(), type(), vars(), zip(), \_\_import\_\_()