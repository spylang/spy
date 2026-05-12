title: The __spy__ Module
---
<style> {
  font-family: "Lucida Console", "Courier New", monospace;
}
</style>

The `__spy__` module provides functions for introspecting and manipulating SPy objects' at colors and types at runtime. It also contains some objects - `interp_list`, `interp_dict`, and `interp_tuple` -  that act as fallback implementations for those data structures that only function within the interpreter.

/// warning
The contents of the `__spy__` module and SPy's builtins form the API surface of a language that's rapidly evolving. All of the constructs, names, functions, or decorators here are likely to change!
///

### __COLOR__(expr) -> Literal["red", "blue"] { #markdown data-toc-label='Color()' }
:   Returns the current color of the passed expression. Mainly useful in tests, but may be useful to give users a view into the color of expressions during development.

### __as_red__(object) -> Literal["red", "blue"] { #markdown data-toc-label='as_red()' }
:   If `object` is a reference type (e.g. strings, int, etc.), `as_red` simply changes the passed object's color to red. If `object` is a value type, returns a copy of the object as a red object. 

: May be useful during metaprograming ensure that blue objects which are equal do not get optimized into the same object at redshift time. See, for example, the [implementation of `exal_expr_List`](https://github.com/spylang/spy/blob/main/spy/vm/astframe.py#L1161).

### __STATIC_TYPE__(object) { #markdown data-toc-label='STATIC_TYPE()' }
:   Returns the type of the expression determined in a static context. Useful in tests, and is used in some of SPy's internal machinery.

### __is_compiled__() { #markdown data-toc-label='is_compiled()' }
:   Returns `False` when run in the interpreter, with or without redshifting. Returns `True` in compiled C code. Useful for testing and benchmarks, where it may be useful to adjust parameters depending on whether the code is compiled or not.


### __interp_list__(object) { #markdown data-toc-label='interp_list' }
:   A `list` object that functions only within the interpreter, and is not supported by the C backend. Highly likely to be removed in the future, but currently useful for prototyping internal to SPy for object types that cannot currently be held in 'real' lists, like types, `object()`s, and dynamic objects.

### __interp_dict__(object) { #markdown data-toc-label='interp_dict' }
:   A `dict` object that functions only within the interpreter, and is not supported by the C backend. Highly likely to be removed in the future, but currently useful for prototyping internal to SPy to support key types that cannot currently be keys of 'real' dicts, like union types.

### __interp_tuple__(object) { #markdown data-toc-label='interp_tuple' }
:   A `tuple` object that functions only within the interpreter, and is not supported by the C backend. Highly likely to be removed in the future, but solves some bootstrapping issues related to other types and operations implemented in SPy.