title: Generic Functions and Types
---
<!-- See https://github.com/spylang/spy/pull/519 and https://github.com/spylang/spy/pull/448-->

### Generic Functions

Functions decorated with [@blue.generic](../api_reference/spy_builtins.md#bluegeneric) are called with `[]` brackets instead of parentheses. These *may* be used anywhere, but they are intended to help create functions that look like [PEP 695](https://peps.python.org/pep-0695/) functions with type parameters:

```python
  @blue.generic
  def add(T):
      def impl(x:T, y: T) -> T:
          return x + y
      return impl

  def main() -> None:
      print(add[i32](1, 2))
      print(add[str]('hello ', 'world'))
```

### Generic Types

`struct` classes may also be created with one or more parameters in `[]` brackets. This is different from passing superclasses inside of `()` parentheses; rather, this is syntactic sugar for a generic function with an inner `struct` class than can make use of those parameters:

```py
@struct
class MyList[T]:
    inner: list[T]
    other_param_1: ...
    other_param_2: ...

# ^^^ is syntactic sugar for vvv

@blue.generic
def MyList(T):
    @struct
    class Self:
        inner: list[T]
        other_param_1: ...
        other_param_2: ...

    return Self
```

In use, this looks like:

```py
@struct
class MyAnnotatedList[T]:
    name: str
    data: list[T]

def main() -> None:
    my_int_list = MyList[i32]("profits", [])
    my_int_list.data.append(1)

    my_str_list = MyList[str]("words", ["hello", "world"])
    my_str_list.data.extend(["and", "goodbye"])
```

### `__origin__`

Objects in SPy have an `__origin__` attribute, which defaults to `None`. When a `type` or `function` defined inside a `blue.generic` function is returned, it's `__origin__` is set to that generic function (if it wasn't already set by something else).

```py
@blue.generic
def adder(T):
    @struct
    class impl:
         ...

    return impl


assert adder[T].__origin__ is adder
```

This is a straightforward way to identify that `MyList[T]` is a 'specialised' version of `MyList` on the type `T`.

This also works with generic classes:

```py
@struct
class MyType[T]:
    inner: list[T]

assert MyList[T].__origin__ is MyList
```