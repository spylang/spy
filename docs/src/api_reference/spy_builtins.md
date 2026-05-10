title: SPy Builtins

<style> {
  font-family: "Lucida Console", "Courier New", monospace;
}
</style>



/// warning
XXXXXXXXXXXXx
///


## Class and Callable Decorators

### __@struct__

:   Used to create a struct from a class definition. See the [low level memory section on structs](/llmem/#stack-allocated-structs) for more details.

### __@blue__
:   Declares that a function should be executed at [redshift time](https://antocuni.eu/2025/10/29/inside-spy-part-1-motivations-and-goals/#redshifting); that is, at the point when method and function lookups are resolved, and prior to compilation to C or WASM, if any.

:   `@blue` decorated functions are not required to specify types for their parameters, nor are they required to specify return types.

### __@blue.generic__
:   Denotes that the decorated function accepts a type as its first argument. Generic functions should return a function object.

:   Generic functions are called using the spy-specific syntax `func[Type](args)`.

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

### @force_inline

:   Causes the decorated functino to be inlined **during redshifting**. 

Only functions with a single return statement at the end of the funciton can be forced inline. Blue functions cannot be forced inline, nor can forced-inline statements be used recursively.

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

