title: Structs
---

Structs (currently the only classes in SPy) are immutable data structures analogous to C structs.

/// warning
Class construction and layout are a part of SPy that's rapidly evolving. All of the constructs, names, functions, or decorators here are likely to change!
///

## Declaration

Structs are declared with the `@struct` decorator on a class definition. Their fixed list of fields follows with type annotations. Note that default values for these fields are not currently supported.

```py
@struct
class Person:
    name: str
    age: int

def main() -> None:
    p = Person('Alice', 99)
    print(p.name, "is", p.age, "years old") # Alice is 99 years old
    
```

Structs may also be defined with the [generic class syntax](../howto/generics.md#generic-class-syntax), which is syntactic sugar for a generic function which defines an internal struct. See the [generics](../howto/generics.md) documentation for more info.

## Attributes

Structs are shallow immutable. Attributes cannot be set after creation, nor can new attributes be assigned to an instance of a struct class after creation:

```py
@struct
class Person:
    name: str
    age: int
    
def main() -> None:
    p = Person('Alice', 99)
    p.name = 'Bob' # TypeError: type `Person` does not support assignment to attribute 'name'
    p.height = 190 # TypeError: type `Person` does not support assignment to attribute 'height'
```



However, objects which are attributes of struct classes may be mutated.

```py
@struct
class Person:
    name: str
    age: int
    books: list[str]


def main() -> None:
    p = Person('Alice', 99, [])
    print(p.name, "has", len(p.books), "book(s)") # Alice has 0 book(s)

    p.books.append("An Introduction to Python")
    print(p.name, "has", len(p.books), "book(s)") # Alice has 1 book(s)
```

If the struct attribute is a pointer to an object, that object at that pointer may also be mutated. (See [Constructors](#constructors) below for info on the `__new__` method):

<!-- TODO once there is reference documentation on pointers/memory, link to it here -->

```py
from unsafe import gc_ptr, gc_alloc

@struct
class Person:
    name: str
    age: gc_ptr[int]

    def __new__(name: str, age: int) -> Person:
        _age = gc_alloc[int](1)
        _age[0] = age
        return Person.__make__(name, _age)

    def do_birthday(self) -> None:
        self.age[0] = self.age[0] + 1


def main() -> None:
    p = Person('Alice', 99)
    print(p.name, "is", p.age[0], "years old") # Alice is 99 years old

    p.do_birthday()
    print(p.name, "is", p.age[0], "years old") # Alice is 100 years old
```

## Pointers to Structs

If a struct is manually allocated using `gc_alloc` or similar, its attributes can be mutated. See the [low level memory docuementary on heap-allocated structs](../llmem.md#heap-allocated-structs) for more info.

```py
from unsafe import gc_alloc, gc_ptr

@struct
class Point:
    x: int

# spy build foo.spy
def main() -> None:
    p = gc_alloc[Point](1)
    p.x = 1
    print(p.x)
    p.x = 2
    print(p.x)
```

## Constructors

Structs use a default constructor which populates all their attributes in-order, and all attributes must be provided each time the default constructor is called. E.g. the example above, the constructor `p = Person('Alice', 99, [])` requires an empty list to be passed for the `books` attribute. We can call this constructor explicitly using the `__make__` method:

```py
@struct
class Person:
    name: str
    age: int
    books: list[str]

def main() -> None:
    p = Person.__make__('Bob', 6, [])
    print(p.age) # 6
```

User-facing constructors can be customized by overwriting the `__new__` method; the `__make__` must be called within to handle the initialization of the complete struct. Note that, as in Python, `__new__` functions like a staticmethod (it does not take a `self` parameter)

```py
@struct
class Person:
    name: str
    age: int
    books: list[str]

    def __new__(name: str, age: int) -> Person:
        _books: list[str] = []
        return Person.__make__(name, age, _books)

def main() -> None:
    p = Person('Alice', 99)
    print(p.name, "has", len(p.books), "books") # Alice has 0 books
```

<!-- 
    TODO Add notes about metafuncs as constructors. This may be more generally useful once typing for things
    like `str | None` is available.
-->

## Methods

Structs may have methods defined inside their class body; the struct object itself is passed as the first parameter (usually called `self`), just as in CPython:

```py
@struct
class Person:
    name: str
    
    def say_hi_to(self, other: Person) -> None:
        print("Hi " + other.name + "! My name is " + self.name)

    def is_teenager(self) -> bool:
        return 13 <= self.age and self.age <= 19

def main() -> None:
    c = Person("Charlie", 55)
    c.say_hi_to(Person("Donna", 57))     # Hi Donna! My name is Charlie
    print(c.is_teenager())               # False
```

Methods may also be [blue functions](../reference/spy_builtin_functions.md#blue), [generic blue functions](../reference/spy_builtin_functions.md#bluegeneric), or [metafunctions](../reference/spy_builtin_functions.md#bluemetafunc).

## Inheritance

Inheriting from a base class is not currently implemented in SPy.

## Structs as Arguments

When used as a function argument, Structs are passed by value, meaning a copy of the struct is created for each call. The performance implications of this should be kept in mind for large structs.