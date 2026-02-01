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

By default, SPy code is **safe**, meanging that:

  1. memory and lifetimes are managed automatically

  2. you cannot corrupt memory or access memory which was already freed

However, SPy also offers the `unsafe` module, for writing low-level code and for
specialized cases.  At the moment of writing, the `unsafe` module can be imported
freely, but the plan is to allow unsafe code only in few specific and clearly labeled
section of the program.


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

Structs have **inline storage**:

  1. if used as local variables, they are allocated "on the stack";

  2. if used as fields of a bigger struct, they are allocated "inline" the bigger
     struct;

  3. they are passed by value, which means that passing around big structs can be
     costly.


For example:

```python
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

  - memory is allocated with `gc_alloc[T]`; pointers are of type `gc_ptr[T]`;

  - the memory is automatically released by the GC when it's no longer needed;

  - it is *still* responsibility of the programmer to avoid out-of-bounds access to
    arrays;

  - objects are potentially **movable** (depending on the GC strategy), so their address
    mght change;

  - it is possible to get a temporary non-movable `raw_ptr` by "pinning" a `gc_ptr` (NOT
    IMPLEMENTED YET!).

/// warning
GC is not implemented yet; currently `gc_alloc` is just an alias to `raw_alloc`,
meaning that it leaks memory
///


## Heap-allocated structs

We can allocated structs "on the heap". This is a lower-level functionality which
requires the use of `unsafe` functions; they can be allocated both in raw and GC memory:

```python
from unsafe import raw_ptr, raw_alloc

p1: raw_ptr[Point] = raw_alloc[Point](1)
p1.x = 1
p1.y = 2
```

Contrarily to their stack-allocated counterparts, heap-allocated structs are mutable.
you should think of heap-allocated structs as the basic building blog for all
higher-level types.

It might be helpful to draw again a parallel to CPython: in CPython, objects of type
`tuple` and `str` are immutable, but under the hood they are implemented by mutable heap
allocated structs written in C.



## Raw allocation

`raw_alloc[T](n)` allocates an **array** of T on the heap. To allocate a single element,
you just pass `n = 1`. For convenience, if T is a struct you can access it's fields
without having to use `[0]`, exactly as in C:

```python
def test(p: raw_ptr[Point]) -> None:
    assert p.x == p[0].x
    assert p.y == p[0].y
```

The low-level representation of pointers depends on the excecution mode.

The interpreter keeps track of the address **and the length** of the allocated region,
and checks for out-of-bounds access:

<div align="right"><sub><a href="https://github.com/spylang/spy/blob/8a360bc11d95db09fee34964ce3cab6639c06f1f/spy/vm/modules/unsafe/ptr.py#L128-L150">See on GitHub</a></sub></div>
```python title="spy/vm/modules/unsafe/ptr.py @ 8a360bc1" linenums="128"
@UNSAFE.builtin_type("__base_ptr")
class W_BasePtr(W_Object):
    [...]
    w_ptrtype: W_BasePtrType
    addr: fixedint.Int32
    length: fixedint.Int32  # how many items in the array
```

The same happens in **debug compiled mode**, where `raw_ptr[T]` is translated to a fat
pointer. Finally, in **release compiled mode**, `raw_ptr[T]` is translated as a plain C
pointer, and there is no out-of-bounds check:


<div align="right"><sub><a href="https://github.com/spylang/spy/blob/8a360bc11d95db09fee34964ce3cab6639c06f1f/spy/libspy/include/spy/unsafe.h#L12-L18">See on GitHub</a></sub></div>
```c title="spy/libspy/include/spy/unsafe.h @ 8a360bc1" linenums="12"
   typedef struct Ptr_T {
       T *p;
   #ifdef SPY_PTR_CHECKED
       size_t length;
   #endif
   } Ptr_T;

```

## GC allocation

**Not implemented yet**

## Raw references: `raw_ref[T]`

Structs and pointers are loosely modeled against C, but there is a big semantic
difference between Python and C that we need to take into account in order to provide an
intuitive way to deal with structs.

Consider the following example, using the `Rect` and `Point` structs defined above. It
modifies a **nested** struct:

```python
def test(r: raw_ptr[Rect]) -> None:
    r.a.x = 0
```

In Python (and thus SPy) the above expression decomposes to:

```python
tmp = r.a
tmp.x = 0
```

or, more explicitly:

```python
tmp = getattr(r, "a")
setattr(tmp, "x", 0)
```

The naive implementation of `r.a` would be to return a *copy* of the `Point` but this
means that `tmp.x` would modify the copy, not the original.

To solve the problem, we return a **reference** instead:

```python
tmp: raw_ref[Point] = r.a
tmp.x = 0
```

Contrarily to pointers, references cannot be indexed and cannot be `NULL`. Moreover, a
`raw_ref[T]` can be automatically converted into a `T`. E.g. consider the following:

```python
def foo(r: raw_ptr[Rect]) -> None:
    r2: Rect = r   # ERROR: cannot convert raw_ptr[Rect] to Rect
    p: Point = r.a  # works: r.a is raw_ref[Point], and it's converted to a Point
```

In the C backend, `raw_ref[T]` is implemented in the exact same way as `raw_ptr[T]`.
