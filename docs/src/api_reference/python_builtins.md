title: CPython-Like Builtins
---

<style>
h3 {
  font-family: "Lucida Console", "Courier New", monospace;
}
</style>

## Implemented CPython-Like Built-ins 

The following built-in functions work similarly to their equivalents in CPython; see the specific functions below for notes

### __abs__(object) { data-toc-label='abs()' }

:   Currently only implemented for int32's or objects convertible to int32's. The `__abs__` attribute is not currently supported.

### __dict__\[type\]() { data-toc-label='dict()' }
:   The syntax `dict[keytype, valuetype]()` can be used to create a new empty dict of the given types; unlike CPython, this does not (currently) accept an Iterable to create a new dict from.

### __float__(object) { data-toc-label='float()' }

:   Converts `object` to a float if able

### __getattr__(obj, name: str) { data-toc-label='getattr()' }

:   `attr` must be blue

### __hash__(object) { data-toc-label='hash()' }
:   Currently implemented for types: `i8`,`i32`, `u8`, `bool`, `str`.

:   By default, instances of SPy classes are not hashable are not hashable. Users can implement the `__hash__` function to permit hashing.

### __int__(object) { data-toc-label='int()' }

:    Converts `object` to an int if able. Works for number types, as well as strings.

:    For conversion to specific integer types, see also [str_to_i32()](), [str_to_u32()](), [str_to_i8()](), [str_to_u8()]().

### __len__(object) { data-toc-label='len()' }

:   Return the length (the number of items) in a container

### __list__\[type\]() { data-toc-label='list()' }

:   The syntax `list[type]()` can be used to create a new empty list of the given type; unlike CPython, this does not (currently) accept an Iterable to create a new list from.

### __max__(x: i32, y: i32) { data-toc-label='max()' }

:   Currently only implemented for int32's or objects convertible to int32's.

### __max__(x: i32, y: i32) { data-toc-label='min()' }

:   Currently only implemented for int32's or objects convertible to int32's.

### __print__(obj) { data-toc-label='print()' }

:   The print function is currently not variadic, in the sense that it only accepts a single argument. The built-in types are special-cased, and SPy can always print blue objects by pre-computing their string representation

### __range__(stop) { data-toc-label='range()' }
<h3> <b>range</b>(start, stop, step) { data-toc-label='' }</h3> <!-- An HTML label to hide this in the TOC -->

Creates an iterable set of indices between `start` and `stop`, jumping over `step` indices between each.

### __repr__(object) { data-toc-label='repr()' }

:   Returns string containing a printable representation of an object.

### __setattr__(object, name: str, value: obj) { data-toc-label='setattr()' }

:   `attr` must be blue

### __slice__(stop) { data-toc-label='slice()' }
<h3><b>slice</b>(start, stop, step=None)</h3> <!-- An HTML label to hide this in the TOC -->

:   Return a slice object representing the items reached when iterating over range(start, stop, step). The start and step arguments default to None.

### __str__(object) { data-toc-label='str()' }

:   Returns a string version of the object. Selecting an encoding is not currently implemented.

### __type__(object) { data-toc-label='type()' }

:   Returns the type (i.e. the dynamic type at runtime) of an object

## Not-Implemented CPython Built-ins 

:   aiter(), all(), anext(), any(), ascii(), bin(), bool(), breakpoint(), bytearray(), bytes(), callable(), chr(), classmethod(), compile(), complex(), delattr(), dir(), divmod(), enumerate(), eval(), exec(), filter(), format(), frozenset(), globals(), hasattr(), help(), hex(), id(), input(), isinstance(), issubclass(), iter(), locals(), map(), memoryview(), next(), object(), oct(), open(), ord(), pow(), property(), reversed(), round(), set(), sorted(), staticmethod(), sum(), super(), tuple(), type(), vars(), zip(), \_\_import\_\_()