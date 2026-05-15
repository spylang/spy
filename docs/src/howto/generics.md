title: Generic Functions and Types
---

<!-- See https://github.com/spylang/spy/pull/519 and https://github.com/spylang/spy/pull/448-->



Geneic 


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

`struct` classes may also be constructed with a type parameter, which is.... At an implementation level, the class syntax syntactic sugar:

```py
@struct
class MyList[T]:
    inner: list[T]

# ^^^ is syntactic sugar for vvv

@blue.generic
def MyList(T):
    @struct
    class Self:
        inner: list[T]

    return Self
```

### \_\_origin\_\_

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


<!-- 

The __origin__ is set ONLY:

upon returning something from a @blue.generic function
if the returned value was defined INSIDE the function
if the __origin__ has not been set already

-->