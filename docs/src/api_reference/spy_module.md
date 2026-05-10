title: The `__spy__` module
---
<style> {
  font-family: "Lucida Console", "Courier New", monospace;
}
</style>

Another class of useful functions is found in the `__spy__` module, available in the SPy standard library.

/// warning
XXXXXXXXXXXXx
///

### __interp_list__(object) { #markdown data-toc-label='interp_list' }
:   xxxx

### __interp_dict__(object) { #markdown data-toc-label='interp_list' }
:   xxxx

### __interp_tuple__(object) { #markdown data-toc-label='interp_list' }
:   xxxx

### __COLOR__(object) -> Literal["red", "blue"] { #markdown data-toc-label='Color()' }
:   Returns the current color of the passed object. Mainly useful in tests, but may be useful to give users a view into the color of their objets during development.

### __as_red__(object) -> Literal["red", "blue"] { #markdown data-toc-label='as_red()' }
:   Returns a copy of the object as a red object. May be useful during metaprograming ensure that blue objects which are equal do not get optimized into the same object at redshift time. See, for example, the [implementation of `exal_expr_List`](https://github.com/spylang/spy/blob/main/spy/vm/astframe.py#L1161).

### __STATIC_TYPE__(object) { #markdown data-toc-label='\_\_STATIC_TYPE\_\_()' }
:   Returns the type of the object determined in a static context. Useful in tests, and used in some of SPy's internal machinery.


