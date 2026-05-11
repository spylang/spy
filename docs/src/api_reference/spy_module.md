title: The __spy__ module
---
<style> {
  font-family: "Lucida Console", "Courier New", monospace;
}
</style>

The `__spy__` module provides functions for introspecting and manipulating SPy objects' at colors and types at runtime. It also contains some objects - `interp_list`, `interp_dict`, and `interp_tuple` -  that act as fallback implementations for those data structures that only function within the interpreter.

/// warning
The contents of the `__spy__` module and SPy's builtins form the API surface of a language that's rapidly evolving. All of the constructs, names, functions, or decorators here are likely to change!
///

### __COLOR__(object) -> Literal["red", "blue"] { #markdown data-toc-label='Color()' }
:   Returns the current color of the passed object. Mainly useful in tests, but may be useful to give users a view into the color of objects during development.

### __as_red__(object) -> Literal["red", "blue"] { #markdown data-toc-label='as_red()' }
:   Returns a copy of the object as a red object. May be useful during metaprograming ensure that blue objects which are equal do not get optimized into the same object at redshift time. See, for example, the [implementation of `exal_expr_List`](https://github.com/spylang/spy/blob/main/spy/vm/astframe.py#L1161).

### __STATIC_TYPE__(object) { #markdown data-toc-label='\_\_STATIC_TYPE\_\_()' }
:   Returns the type of the object determined in a static context. Useful in tests, and is used in some of SPy's internal machinery.

### __interp_list__(object) { #markdown data-toc-label='interp_list' }
:   A `list` object that functions only within the interpreter, and is not supported by the C backend. Highly likely to be removed in the future, but currently useful for prototyping internal to SPy for object types that cannot currently be held in 'real' lists, like types, `object()`s, and dynamic objects.

### __interp_dict__(object) { #markdown data-toc-label='interp_dict' }
:   A `dict` object that functions only within the interpreter, and is not supported by the C backend. Highly likely to be removed in the future, but currently useful for prototyping internal to SPy to support key types that cannot currently be keys of 'real' dicts, like union types.

### __interp_tuple__(object) { #markdown data-toc-label='interp_tuple' }
:   A `tuple` object that functions only within the interpreter, and is not supported by the C backend. Highly likely to be removed in the future, but solves some bootstrapping issues related to other types and operations implemented in SPy.