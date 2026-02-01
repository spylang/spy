# Low-level memory model

SPy aims to be a "two-level" language, with a low-level, possibly unsafe core, upon
which to build higher level abstractions which we expect end users to use.

It might help to draw a parallel with CPython: the core of the interpreter and of many
libraries is written in C, which is low level and inherently unsafe. The result is a
safe high-level language which is what most people see and use.

This document describes the low-level memory model of SPy.

While reading this document, it is worth remembering that SPy has two main mode of
execution, interpreted and compiled.

The SPy compiler works by translating `*.spy` code into `*.c` code (after
[redshifting](https://antocuni.eu/2025/10/29/inside-spy-part-1-motivations-and-goals/#redshifting)),
which is then compiled by e.g. `gcc` or `clang`.  In the next sections, we will also
explain how SPy types are translated into C.

## Save vs unsafe code

XXX I don't like this section

By default, SPy code is **safe**, meanging that:

  1. memory and lifetimes are managed automatically

  2. you cannot corrupt memory or access memory which was already freed

However, SPy also offers the `unsafe` module, for writing low-level code and for
specialized cases.  The level of safety depends on how the code is run: the
**interpreted** and the **debug compiled** modes tries to catch as many bugs as
possible. The **release mode** is actually unsafe.


## Raw and GC memory

The heap is conceptually divided into two main regions: **raw memory** and **GC memory**.
The low-level manipulation of both areas of memory is **unsafe**.

Raw memory is "C style":

  - memory is allocated with `raw_alloc[T]`; pointers are of type `raw_ptr[T]`;

  - the memory must be explicitly released by calling `raw_free[T]` (NOT IMPLEMENTED
    YET!)

  - it is responsibility of the programmer to avoid use-after-free and out-of-bounds
    access;

  - once allocated, the address of the memory is non-movable and can be safely passed to
    3rd party libraries

GC memory:

  - memory is allocated with `gc_alloc[T]`; pointers are of type `ptr[T]`;

  - the memory is automatically released by the GC when it's no longer needed;

  - it is *still* responsibility of the programmer to avoid out-of-bounds access to
    arrays;

  - objects are potentially **movable** (depending on the GC strategy), so their address
    mght change;

  - it is possible to get a temporary non-movable `raw_ptr` by "pinning" the GC `ptr`.


## Primitive types

At the core, we have primitive numeric types such as `i32`, `f32`, `f64`, etc. These are
translated into their C equivalent `int32_t`, `float`, `double`, etc.

Moreover, SPy defines the `int` and `float` aliases, which maps to `i32` and `f64`
respectively. At the moment this is hardcoded, but eventually the precise mapping will
depend on the target platform:


<div align="right"><sub><a href="https://github.com/spylang/spy/blob/37ee3e29a7707618adf107ca7d8d19de2942ab55/spy/vm/modules/builtins.py#L222-L230">See on GitHub</a></sub></div>

```python title="spy/vm/modules/builtins.py @ 37ee3e29" linenums="222"
# add aliases for common types. For now we map:
#   int -> i32
#   float -> f64
#
# We might want to map int to different concrete types, depending on the
# platform? Or maybe have some kind of "configure step"?
BUILTINS.add("int", BUILTINS.w_i32)
BUILTINS.add("float", BUILTINS.w_f64)
```

## Stack-allocated structs

We can define C-like structs:

```python
@struct
class Point:
    x: int
    y: int
```

Structs can be instantiated directly, and are **immutable**:

```python
p = Point(1, 2)
print(p.x, p.y)

p.x = 3 # TypeError
```

Structs have **inline storage**, meaning that:

  1. they are allocated "on the stack";

  2. they are passed by value, which means that passing around big structs can be
     costly;

  3. if used as fields of a bigger struct, they are allocated "inline" the bigger
     struct.

For example:

```
@struct
class Rect:
    a: Point
    b: Point

assert sizeof(Point) == sizeof(int) * 2
assert sizeof(Rect) == sizeof(int) * 4

r = Rect(Point(1, 2), Point(3, 4))
```

The compiler translates them into plain C structs, something along these lines:

```c
typedef struct {
    int32_t x;
    int32_t y;
} Point;

typedef struct {
    Point a;
    Point b;
} Rect;

Point p = {1, 2};
Rect r = {(Point){1, 2}, (Point){3, 4}};
```

Stack-allocated structs are always safe to use.


## Heap-allocated structs

We can allocated structs "on the heap". This is a lower-level functionality which
requires the use of `unsafe` functions:

```python
from unsafe import raw_ptr, raw_alloc

p: raw_ptr[Point] = raw_alloc[Point](1)
p.x = 1
p.y = 2
```

Contrarily to their stack-allocated counterparts, heap-allocated structs are
mutable. This is the basic building



## Raw memory vs GC memory


`raw_alloc[T]` is more or less a typed version of C's `malloc()`. It allocates an
**array** of structs on the heap.

xxx
