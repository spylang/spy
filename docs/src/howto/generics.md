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

Like all functions marked `@blue`, the generic function is guarenteed to be executed at compile-time. We can see in the redshifted version of the above code that `add()` no longer appears, but the two specialized versions of it remain:

<!-- Colorful code formatted by ansi2html -->
<style type="text/css">
.ansi2html-content { display: block; white-space: pre-wrap; word-wrap: break-word; font-size: .85em; padding:1.1em; corner-radius: 0.1em}
.ansi32 { color: #00aa00; }
.ansi33 { color: #aa5500; }
.ansi34 { color: #0000aa; }
.ansi35 { color: #E850A8; }
</style>
<div class="body_background" style="background-color:rgb(245, 245, 245);">
<pre class="ansi2html-content">
<span class="ansi34">def</span> main() -&gt; <span class="ansi34">None</span>:
    <span class="ansi35">`_print::println[i32]::p`</span>(<span class="ansi35">`t::add[i32]::impl`</span>(<span class="ansi33">1</span>, <span class="ansi33">2</span>))
    <span class="ansi35">`_print::println[str]::p`</span>(<span class="ansi35">`t::add[str]::impl`</span>(<span class="ansi32">'hello '</span>, <span class="ansi32">'world'</span>))

<span class="ansi34">def</span> <span class="ansi35">`t::add[i32]::impl`</span>(x: <span class="ansi35">i32</span>, y: <span class="ansi35">i32</span>) -&gt; <span class="ansi35">i32</span>:
    <span class="ansi34">return</span> x + y

<span class="ansi34">def</span> <span class="ansi35">`t::add[str]::impl`</span>(x: <span class="ansi35">str</span>, y: <span class="ansi35">str</span>) -&gt; <span class="ansi35">str</span>:
    <span class="ansi34">return</span> <span class="ansi35">`operator::str_add`</span>(x, y)
</pre>
</div>

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
class MyNamedList[T]:
    name: str
    data: list[T]

def main() -> None:
    my_int_list = MyNamedList[i32]("profits", [])
    my_int_list.data.append(1_000_000)

    my_str_list = MyNamedList[str]("words", ["hello", "world"])
    my_str_list.data.extend(["and", "goodbye"])
```

### `__origin__`

The `__origin__` attribute of SPy objects carries information about the generic function which created them, if any. When `blue.generic` defines a `type` or `function` and returns it, the returned object has it's `__origin__` is set to the generic function:

```py
@blue.generic
def adder(T):
    @struct
    class impl:
         ...

    return impl


def main() -> None:
    assert adder[T].__origin__ is adder
```

This is a straightforward way to identify that, for example, `MyList[T]` is a 'specialised' version of `MyList` on the type `T`.

(The default value for `__origin__` is None. If the object returned by a generic function already has a non-`None` origin, that origin will *not* be overwritten.)

This also works with the generic class syntax:

```py
@struct
class MyList[T]:
    inner: list[T]

def main() -> None:
    assert MyList[i32].__origin__ is MyList
```