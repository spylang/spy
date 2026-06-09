title: SPy Builtins

<style> {
  font-family: "Lucida Console", "Courier New", monospace;
}
</style>

SPy adds several new builtins to the global namespace. Currently, all of them happen to be decorators for classes or callables.

/// warning
The contents of the `__spy__` module and SPy's builtins form the API surface of a language that's rapidly evolving. All of the constructs, names, functions, or decorators here are likely to change!
///

/// important
For a deeper explanation of the current state of SPy's coloring nomenclature, see [this post by Antonio Cuni](https://antocuni.eu/2026/03/25/inside-spy-part-2-language-semantics/#blue-functions).
///


## Class and Callable Decorators

### __@struct__

:   Used to create a struct from a class definition. See the [low level memory section on structs](../llmem.md#stack-allocated-structs) for more details.

### __@blue__
:   Declares that a function should be executed at [redshift time](https://antocuni.eu/2025/10/29/inside-spy-part-1-motivations-and-goals/#redshifting); that is, at the point when method and function lookups are resolved, and prior to compilation to C or WASM, if any.

:   type annotations for `@blue` functions are optional. If omitted, the arguments and return types default to `dynamic`.

: In this example, the two blue functions are evaluated during redshift time, and the emitted C code is just a print statement of a constant number.

```py
@blue
def factorial(x)
    if x == 0: return 1
    if x == 1: return 1
    return x * factorial(x-1)

@blue
def calc_e(terms):
    sum: float = 0
    for i in range(terms):
        sum += 1/factorial(i)
    return sum

def main() -> None:
    print(calc_e(10))
```

### __@blue.generic__
:   Functions decorated with `@blue.generic` are called using square brackets `[]` instead of parentheses `()`. Other than that, they are identical to other blue functions. While they may be used anywhere, the primary purposes is to allow the creation of functions that look like [PEP 695](https://peps.python.org/pep-0695/) functions with type parameters:

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

### __@blue.metafunc__
:   Unlike `blue.generic` functions, `metafunc`s accept one or more arguments, and return an [OpSpec]() appropriate to those arguments based on their static type.

```python
  from operator import OpSpec

  @blue.metafunc
  def myprint(m_x):
      if m_x.static_type == int:
          def myprint_int(x: int) -> None:
              print(x)
          return OpSpec(myprint_int)

      if m_x.static_type == str:
          def myprint_str(x: str) -> None:
              print(x)
          return OpSpec(myprint_str)

      raise TypeError("don't know how to print this")

  def main() -> None:
      print(42)
      myprint("hello")
      myprint(5.2)  # raises TypeError
```

### __@force_inline__

:   Causes the decorated function to be inlined **during redshifting**. 

:   Only functions with a single return statement at the end of the function can be forced inline. Blue functions cannot be forced inline, nor can forced-inline statements be used recursively.

```py
#inline_demo.spy
from __spy__ import force_inline

@force_inline
def inc(x: i32) -> i32:
    return x + 1

def main() -> None:
    print(inc(1))
```
```sh
# spy rs inline_demo.spy
def main() -> None:
    `_print::_print_one[i32]::impl`(__block__(x$0: i32 = 1; x$0 + 1))
```

