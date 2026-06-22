title: Generic Functions and Types
---
<!-- See https://github.com/spylang/spy/pull/519 and https://github.com/spylang/spy/pull/448-->

### Generic Functions

Functions decorated with [@blue.generic](../reference/spy_builtin_functions.md#bluegeneric) are called with `[]` brackets instead of parentheses. These *may* be used anywhere, but they are intended to help create functions that look like [PEP 695](https://peps.python.org/pep-0695/) functions with type parameters:

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

Like all functions marked `@blue`, the generic function is guaranteed to be executed at compile-time. We can see in the redshifted version of the above code that `add()` no longer appears, but the two specialized versions of it remain:

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

### Generic Class Syntax

`@struct` classes may also be created with one or more parameters in `[]` brackets. This is different from passing superclasses inside of `()` parentheses; rather, this is syntactic sugar for a generic function with an inner `@struct` class than can make use of those parameters:

```py
@struct
class MyList[T]:
    inner: list[T]
    other_param_1: ...
    other_param_2: ...

# ↑ is syntactic sugar for ↓

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

For a larger example, see the `myarray` example [on GitHub](https://github.com/spylang/spy/blob/main/examples/myarray.spy) or [run it in the SPy Playground](https://spylang.github.io/spy/#code=eJydVcFO40AMvecrrHBpdiGiwHKoFsRKcOCCkOCyQlVkEqed3XQmmplQytevJ5OmkzZIK6oeEnv8bL9nT-I4jp6XwgD_lSRQJdglwUoZC1i8ocypAHrHVV2Rcd6nxw0YBSXqNIruLQjnWZG0pg18RSPy9iDCgiRpkQNqjRuwm5qi6EFZ4oNowVjd5JxEE9RoDKd53cAbVg3nmYiUUshVLahI0ijmIqNSqxU00mBJLqnSFhZ5hlWl8mP3VFsdRdGNh43yijHhl8t8ixZfbp9_P97NZxHwryK5sMsZiPOz9j3HGnNhNzuLsLQysw61i2XweEvWtjOfhQ1_GubLbKTF3LLdNAvUUCqu6OaVO0q7gKigclfUpAVOfFHbwtuCWtgnqkrvGyt6vPDPi3ceTbbRsgUOlXC6SVz14udK5nyUWslcd1itcWMgdoFxJ8cY09NiwPMRo3F0J7TDcQYJH6TVSe4mbK2xrknzEKhGFm3yOMuqKstiqJWQlnQKz2xlWhusoGDWHNCSsD5ppUdLRdpm83F93_vSdxQcgeS-Z4yg6bhlgtvVmkytZMEjrEYYGPaWeiCnZJZJWmfZJNAmgZPrPeWOuO-uGcZfoy78qvi1cC3tRK7gqp_qwxYm0yQ4mvq0HOEfQtd2Mkad7YCEiTx818YuheAzp_3beikqngb4uR3F3hPCvoj5IGqLI-A7THtrMIhplq3wLzkWq2RHrZsLWUwMnzj2t8IM_Lo4gh_4qpoNWTMey83AroEyoOn6KiRmWP0RV2TEB68BUcE30QkUqnmtyA9DFzKIcMKHJAeUf4OzYfvl3mnmZ5h-BHB6kO0z1cLAZK8rvkE3fHsLY4Vc-IvhQJmhVoHKW-bGaw3UDrQ_OHqovVesH8Iea_9AQEbYYnQwyS99pa6YdlbGt6R_duUES7wg64B4BP24id0mtxz_36SJbsLGSNMoDMG9LOj9Tmv-LPQOvwghg0FhZrQw3oev7cKXKhwu9htf_K62FQo52UuPWVkptE7U7Y1ZXl7wpXWadH4hB17uZT65CJ0vp_N-9jvL1FnOQsuZs5yHlnNnuQgsaXd9_EhGjJfeyF9nZoQ_Rxrlgti6I6TWfH7SgYt5Ev0DKx6k_A==)

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

(The default value for `__origin__` is `None`. If the object returned by a generic function already has a non-`None` origin, that origin will *not* be overwritten.)

The `__origin__` functions identically with the Generic Class syntax described above:

```py
@struct
class MyList[T]:
    inner: list[T]

def main() -> None:
    assert MyList[i32].__origin__ is MyList
```