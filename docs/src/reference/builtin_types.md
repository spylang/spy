title: Built-in Types
---

## Type Objects

Types are first class objects in SPy - they can be passed, modified, printed etc. just like any other object. The dynamic type of an object can be retrieved using the [type()](../reference/python_builtins.md#typeobject) builtin

SPy types have attributes that are not present on other objects for identifying the type by name, either for human-readability or identifying the functions origin. A brief example:

```py
#a.spy

@struct
class Foo[T]:
    pass

def main() -> None:
    print("__name__     ", Foo[i32].__name__)
    print("__fqn__      ", Foo[i32].__fqn__)
    print("__qualname__ ", Foo[i32].__qualname__)
    print("__full_fqn__ ", Foo[i32].__full_fqn__)
```
```
# result 
__name__      Foo[i32]
__fqn__       a::Foo[i32]
__qualname__  a::Foo[i32]
__full_fqn__  a::Foo[i32]::Self
```

### \_\_name\_\_

:   The name of the type object, along with any qualifiers (e.g. additional parameters for generic types).

### \_\_fqn\_\_

:   The Fully Qualified Name of the type object, including the module it originates from. 

### \_\_qualname\_\_

:   An alias to `__fqn__`

### \_\_full_fqn\_\_

:   An expended representation of the FQN, and the most complete name used in the SPy internals. This is what is shown when running `spy redshift --full-fqn`.


