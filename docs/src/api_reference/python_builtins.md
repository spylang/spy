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

### __breakpoint()__

:   Drops the user into an interactive SPy debugging session via `spdb`, a `pdb-like` debugging interface for SPy.

### __dict__\[keytype, valuetype\]() { data-toc-label='dict()' }
:   In SPy, `dict` must always be fully typed and used as `dict[keytype, valuetype]`., The syntax `dict[keytype, valuetype]()` can be used to create a new empty dict of the given types. The simpler syntax `d: dict[keytype, valuetype] = {}` can also be used.

:   Unlike CPython, this does not (currently) accept an Iterable to create a new dict from.

:   The implementation (in SPy) of `dict` can be [viewed here](https://github.com/spylang/spy/blob/main/stdlib/_dict.spy).

### __dir__(object) {data-toc-label='dir()'}

:   Returns a list of object’s attributes’ names, the names of its class’s attributes, and recursively of the attributes of its class’s base classes. `dir(type)` is not currently implemented.

:   The no-argument form of `dir()` (i.e. print local variables) is not currently implemented. Custom `__dir__` methods on objects are not currently supported.

### __float__(object) { data-toc-label='float()' }

:   Converts `object` to a float if able. `float` is an alias for the `f64` type.

### __getattr__(obj, name: str) { data-toc-label='getattr()' }

:   Return the value of the named attribute of object. `attr` must be blue

### __hash__(object) { data-toc-label='hash()' }
:   Currently implemented for types: `i8`,`i32`, `u8`, `bool`, `str`.

:   By default, instances of SPy structs are not hashable. As a planned future feature, structs will have auto-generated `__hash__` by default, but this is awaiting implementation. Currently, users can implement the `__hash__` function to permit hashing. 

### __int__(object) { data-toc-label='int()' }

:   Converts `object` to an int if able. Works for number types, as well as strings.

:   The `int` type is currently an alias to `i32`. In the future, `int` will alias preferred individual types for specific platforms, but currently it is always `i32`.

### __len__(object) { data-toc-label='len()' }

:   Return the length (the number of items) in a container

### __list__\[type\]() { data-toc-label='list()' }

:   The syntax `list[type]()` can be used to create a new empty list of the given type. The simpler syntax `l: list[membertype] = []` can also be used. Unlike CPython, this does not (currently) accept an Iterable to create a new list from. 

:   The implementation (in SPy) of `list` can be [viewed here](https://github.com/spylang/spy/blob/main/stdlib/_list.spy).

### __max__(x: i32, y: i32) { data-toc-label='max()' }

:   Currently only implemented for int32's or objects convertible to int32's.

### __min__(x: i32, y: i32) { data-toc-label='min()' }

:   Currently only implemented for int32's or objects convertible to int32's.

### __object__

:   `object` is implemented as a type, and can be used as a parameter or return type. "Plain" objects (i.e. `x = object()`) are not supported.

### __print__(obj) { data-toc-label='print()' }

:   The print function is currently not variadic, in the sense that it only accepts a single argument. The built-in types are special-cased, and SPy can always print blue objects by pre-computing their string representation

### __range__(stop) { data-toc-label='range()' }
<h3> <b>range</b>(start, stop, step)</h3> <!-- An HTML label to hide this in the TOC -->

:   Creates an iterable set of indices between `start` and `stop`, jumping over `step` indices between each.

:   The implementation (in SPy) of `range` can be [viewed here](https://github.com/spylang/spy/blob/main/stdlib/_range.spy).

### __repr__(object) { data-toc-label='repr()' }

:   Returns string containing a printable representation of an object.

### __setattr__(object, name: str, value: obj) { data-toc-label='setattr()' }

:   Assigns `value` to the attribute of `object` named by `name`. `attr` must be blue.

### __slice__(stop) { data-toc-label='slice()' }
<h3><b>slice</b>(start, stop, step=None)</h3> <!-- An HTML label to hide this in the TOC -->

:   Return a slice object representing the items reached when iterating over range(start, stop, step). The start and step arguments default to None.

### __str__(object) { data-toc-label='str()' }

:   Returns a string version of the object. Selecting an encoding is not currently implemented.

### __tuple__()

:   The syntax `tuple[t1, t2, ...](val1, val2 ...)` can be used to create a new tuple, with `t1` as the type of `val1`, etc. unlike CPython, this does not (currently) accept an Iterable to create a new tuple from. 

:   The implementation (in SPy) of `tuple` can be [viewed here](https://github.com/spylang/spy/blob/main/stdlib/_tuple.spy).

### __type__(object) { data-toc-label='type()' }

:   Returns the type (i.e. the dynamic type at runtime) of an object

## Not-Implemented CPython Built-ins 

The following CPython built-ins are not currently implemented in SPy. Each category has a brief note about the current state of that category of object or function - some require additional internal mechanics, others are simply lower priority that other facets of the language to this point.

### Async

SPy does not currently have an async story.

:   aiter(), anext()

### Iterables and Iterators

Iterables and collections are very much an area of active developmen; as their API solidifies, these types of builtins should become more straightforward to implement.

Generators are not currently supported in SPy.

:   all(), any(), enumerate(), filter(), iter(), map(), next(), reversed(), sorted(), sum(), zip()

### Math

Number types beyond int and float are in active development; some of the math functions below are also in active development.

:   divmod(), bin(), hex(), oct(), pow(), round()

### Function Types, Introspection and Metaprogramming

The internals of SPy are significantly different from CPython; as such, the road to (and need for) some of these built-ins is less straightforward. Some are also waiting on internal details to solidify prior to implementation.

:   callable(), classmethod(), compile(), delattr(), eval(), exec(), globals(), hasattr(), help(), id(), isinstance(), issubclass(), locals(), property(), super(), vars(). \_\_import\_\_()

### Type Conversion

Many of these types are not implemented yet; others are in active development.

:   ascii(), bool(), bytearray(), bytes(), chr(), complex(), format(), frozenset(), memoryview(), ord() set()

### I/O

The I/O story is currently a high priority and is in active development.

:   input(), open()