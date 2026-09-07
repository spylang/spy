title: Scoping rules
---

Scoping rules in SPy are somewhat complex and are the result of a tension between two
conflicting goals:

- have "sane" scoping rules, similar to what you have in other statically typed
  languages. In particular, we want explicit declarations and block-level scoping;

- preserve the "python feeling" whenever possible, including implicit declarations and a
  limited form of type inference

This is achieved by having two scoping modes:

- **Strict scoping** is the explicit core: every binding is introduced by an explicit
  `var` or `const` declaration. It stands on its own and has no Python-specific magic.
  It can be enabled by using `from __spy__ import strict_scoping`.

- **Pythonic scoping** is sugar on top of strict scoping, defined by desugaring every
  implicit binding to an explicit one. It is the default.

This document describes strict scoping first, and then shows how we implement Pythonic
scoping by desugaring implicit declarations into explicit ones.

## Part 1 - Strict scoping

### `[decl.forms]` Declaring a name { #decl-forms }

The full form of a declaration is:

```
MODIFIER name: TYPE = initializer
```

`MODIFIER` can be:
  - `const`: the name is assigned only once
  - `var`: the name can be reassigned

In strict scoping, `MODIFIER` is mandatory. Under pythonic scoping it can be
omitted and inferred from the number of assignments, see
[`[sugar.constness]`](#sugar-constness).

If `TYPE` is `auto`, the type is inferred. If `TYPE` is omitted it's the same as `auto`.

`initializer` can be omitted.

The following are valid declarations:
```python
def f() -> None:
    var a: int = 42    # full form
    const b: int = 43  # cannot be re-assigned
    var c: auto = 44   # inferred type
    var d = 45         # same as above
    var e: auto        # same as above, will be initialized later
```


### `[decl.initializer]` The initializer may be omitted { #decl-initializer }

```python
def f() -> None:
    var x: i32
    x = 1
    print(x)             # 1
```

### `[decl.uninitialized-read]` Reading uninitialized variables { #decl-uninitialized-read }

With the current rules, it might happen to read an uninitialized variable:
```python
def f() -> None:
    var x: i32
    if False:
        x = 42
    print(x)             # runtime error / UB: `i` may be unassigned
```

This error is caught at runtime by the interpreter, and results in UB in compiled mode.
This is a temporary limitation of SPy. Eventually we will implement
[`[future-definite-assignment]`(#future-definite-assignment).


### `[decl.type-inference]` `auto` defers the type to the first assignment { #decl-type-inference }

Without an initializer there is nothing to infer the type from at the declaration site,
so the type must be given explicitly as `auto`.

```python
def f(cond: bool) -> None:
    var x: auto
    x = 1            # fixes x: i32
    print(x)
```

### `[scope.block]` Blocks are scopes { #scope-block }

The bodies of `if` / `elif` / `else` / `for` / `while` each introduce a scope.

```python
def f(cond: bool) -> None:
    if cond:
        const x: i32 = 1
        print(x)         # 1
    print(x)             # ERROR: `x` not in scope
```

```python
def f() -> None:
    while True:
        var x: i32 = 1
        break
    print(x)             # ERROR: `x` not in scope
```

### `[scope.shadow]` An inner block may shadow an outer name { #scope-shadow }

```python
def f(cond: bool) -> None:
    const x: i32 = 42
    if cond:
        const x: str = "hi"
        print(x)         # "hi"
    print(x)             # 42
```


### `[scope.loop-target]` A loop target dies with its block { #scope-loop-target }

```python
def f() -> None:
    for i in range(10):
        pass
    print(i)             # ERROR: `i` is local to the `for` body
                         #        help: declare `var i: auto` before the loop
```

### `[scope.loop-target-declare]` Declaring the target first makes it outlive the loop { #scope-loop-target-declare }

A loop target is an ordinary assignment: if a binding of the same name already
exists in an enclosing block, the loop reuses it instead of creating a fresh
block-local.

```python
def f() -> None:
    var i: auto
    for i in range(3):
        pass
    print(i)             # OK: 2
```

If the target is declared with a type, the element type must match it:

```python
def f() -> None:
    var i: str
    for i in range(10):  # ERROR: expected `str`, got `i32`
        pass
```

An empty iterable leaves it unassigned, see
[`[decl.uninitialized-read]`](#decl-uninitialized-read).

### `[decl.no-redeclare]` No re-declaration in the same scope { #decl-no-redeclare }

```python
def f() -> None:
    var x: i32 = 0
    var x: i32 = 1       # ERROR: `x` already declared
```

### `[scope.branch-local]` A branch declaration is branch-local { #scope-branch-local }

Each branch is its own scope, so neither declaration survives the `if`:

```python
def f(cond: bool) -> None:
    if cond:
        var x: i32 = 1
    else:
        var x: i32 = 2
    print(x)             # ERROR: `x` not in scope
```

Declare it before the `if` to share one binding:

```python
def f(cond: bool) -> None:
    var x: i32
    if cond:
        x = 1
    else:
        x = 2
    print(x)             # OK
```


```python
def f() -> None:
    var x: i32 = 1
    for i in range(3):
        var x: i32 = i * 10
        print(x)         # 0, 10, 20
    print(x)             # 1
```

### `[scope.sibling-reuse]` Sibling blocks may reuse a name at different types { #scope-sibling-reuse }

```python
def f(cond: bool) -> None:
    if cond:
        var x: i32 = 1
    else:
        var x: str = "hi"
```

### `[name.resolution]` Names resolve outward, lexically { #name-resolution }

```python
const K: i32 = 42

def f() -> None:
    print(K)             # OK
    print(nope)          # ERROR: NameError
```

### `[name.class-skip]` Class scopes are skipped by method bodies { #name-class-skip }

```python
@struct
class P:
    x: i32
    def get(self) -> i32:
        return x         # ERROR: NameError (use `self.x`)
```

### `[closure.nonlocal]` Closures read outer names freely; writing needs `nonlocal` { #closure-nonlocal }

Under strict scoping a bare assignment declares nothing, so writing an outer
name requires `nonlocal`. (Under pythonic scoping the bare form is a fresh
local instead, see [`[sugar.shadow-write]`](#sugar-shadow-write).)

```python
from __spy__ import strict_scoping

def outer() -> None:
    var x: i32 = 0
    def inner() -> None:
        print(x)         # OK: read capture
    def bad() -> None:
        x = 1            # ERROR: `x` is not declared; say `nonlocal x`
    def good() -> None:
        nonlocal x
        x = 1            # OK
```

`nonlocal` / `global` only re-target the assignment; they do not grant
mutability:

```python
A = 1                    # const

def main() -> None:
    global A
    A = 0                # ERROR: `A` is a const (help: declare it `var A`)
```

### `[decl.type-fixed]` The declared type never moves { #decl-type-fixed }

This is what makes the model implementable without CFGs or fixpoint analysis.

```python
def f() -> None:
    var x: i32 = 0
    x = 1                # OK
    x = "hi"             # ERROR: expected `i32` because of type declaration
```

A wide declared type is how you get a wide variable:

```python
def f(cond: bool) -> None:
    var x: i32 | str
    if cond:
        x = 1
    else:
        x = "hi"
    print(x)             # x: i32 | str, the declared type
```

### `[decl.use-before]` A name may not be used before its declaration { #decl-use-before }

This keeps the meaning of a name constant within a block: the reference does
not fall through to the outer `x`.

```python
def f(cond: bool) -> None:
    var x: i32 = 1
    if cond:
        print(x)         # ERROR: `x` used before its declaration in this block
        var x: str = "hi"
```

The same holds when the declaration comes later in an *enclosing* block:

```python
A = 1

def main(cond: bool) -> None:
    if cond:
        print(A)         # ERROR: `A` is declared later in this function
    A = 0
```

### `[class.flat-body]` Class bodies are not blocks { #class-flat-body }

Field declarations bind in the class scope whatever their nesting.

```python
@struct
class P:
    x: i32
    if COND:
        y: i32           # OK: still a field of P
```

### `[scope.loop-fresh]` A block-local is fresh on each loop iteration { #scope-loop-fresh }

```python
def f() -> None:
    for i in range(3):
        var x: i32
        if i == 0:
            x = 1
        print(x)         # i == 1: `x` is unassigned, not 1
```

## Part 2 - Pythonic scoping

Sugar over strict scoping: every rule below has an explicit equivalent, and
`from __spy__ import strict_scoping` removes it.

### `[sugar.first-assign]` The first assignment declares { #sugar-first-assign }

```python
def f() -> None:
    x = 0                # like: const x: i32 = 0
    print(x)
```

A later assignment is a reassignment, not a new declaration:

```python
def f() -> None:
    x = 0                # like: var x: i32 = 0
    x = x + 1
```

Unpacking targets are implicit declarations too:

```python
def f() -> None:
    t = 1, 2
    a, b = t
    print(a)             # 1
```

### `[sugar.def-class]` A nested `def` or `class` is a binding like any other { #sugar-def-class }

There is no special case: it follows the same rules as other assignments, so
it is block-local, and eligible for promotion
([`[sugar.promotion]`](#sugar-promotion)).

```python
COND = True

def main() -> None:
    if COND:
        def g() -> i32:
            return 42
    print(g())           # ERROR: `g` is local to the `if` body
```

```python
def main() -> None:
    if COND:
        def g() -> i32: return 42
    else:
        def g() -> i32: return 0
    print(g())           # OK: promoted
```

### `[sugar.walrus]` A walrus binds in the enclosing block { #sugar-walrus }

The test is not part of either body.

```python
def main() -> None:
    if (x := 5) > 0:
        print(x)         # 5
    print(x)             # 5
```

```python
def f() -> None:
    while (n := next_one()) > 0:
        print(n)
    print(n)             # OK: n lives in the function block
```

### `[sugar.constness]` `var` / `const` is inferred from the number of assignments { #sugar-constness }

Not to be confused with mutability of values: this is about whether the
*name* is rebound, not whether the object it refers to can be mutated.
Assigned once → `const`; assigned more than once → `var`.

```python
def f() -> None:
    a = 1                # const
    b = 1                # var
    b = b + 1
    c = 1                # var
    c += 1
```

The same inference applies to a declaration that has a type but no modifier
(see [`[decl.forms]`](#decl-forms)):

```python
def f() -> None:
    a: i32 = 1           # const
    b: i32 = 1           # var
    b = b + 1
```

### `[sugar.constness-paths]` The count is per execution path { #sugar-constness-paths }

A statement sequence sums; an `if` chain takes the max over its branches.

```python
def f(cond: bool) -> None:
    if cond:
        n = 0            # one assignment on either path → const
    else:
        n = 1
```

```python
def f(cond: bool) -> None:
    if cond:
        n = 0
    else:
        n = 1
    n = 2                # now two on every path → var
```

A parameter counts as one assignment at entry, so assigning to it makes it
`var`:

```python
def f(x: i32) -> None:   # x: const
    print(x)

def g(x: i32) -> None:   # x: var
    x = x + 1
```

A declaration counts one only if it has an initializer:

```python
def f(cond: bool) -> None:
    var x: i32           # zero
    if cond:
        x = 1            # one on this path
```

### `[sugar.blue-params]` Blue parameters are always `const` { #sugar-blue-params }

```python
@blue
def h(x: i32) -> None:
    x = x + 1            # ERROR: blue function arguments are const by default
```

### `[sugar.module-level]` Module level is `const` unless you write `var` { #sugar-module-level }

```python
A = 1                    # const
var B: i32 = 2           # var
```

```python
A = 1
A = 2                    # ERROR: `A` already declared
```

### `[sugar.augassign]` `AugAssign` needs an existing binding { #sugar-augassign }

```python
def f() -> None:
    x += 1               # ERROR: name `x` is not defined
```

### `[sugar.blue-const]` `const` is what makes a value usable at blue time { #sugar-blue-const }

A `const` holding a blue value stays blue.

```python
TUP = 1, 2.5, "hello"

@blue
def f() -> None:
    n = 2                # const → blue
    print(TUP[n])        # "hello"
```

```python
@blue
def f() -> None:
    n = 2                # var → red
    n = n + 0
    print(TUP[n])        # ERROR: tuple index must be blue
```

### `[sugar.loop-target-scope]` A loop target binds in the loop block { #sugar-loop-target-scope }

The next loop may therefore reuse the name at a different type.

```python
def f() -> None:
    for i in [1, 2, 3]:
        print(i)         # i: i32
    for i in ["a", "b"]:
        print(i)         # i: str, a different binding
```

### `[sugar.loop-target-declare]` Declaring the target first makes it outlive the loop { #sugar-loop-target-declare }

```python
def f() -> None:
    var i: auto
    for i in range(3):
        pass
    print(i)             # OK: 2
```


If the target is declared with a type, the element type must match it:

```python
def f() -> None:
    var i: str
    for i in range(10):  # ERROR: expected `str`, got `i32`
        pass
```

The reuse looks only at enclosing blocks of the same function, never at an
outer function or module scope:

```python
var i: i32 = 99

def f() -> None:
    for i in range(3):   # fresh loop-local; the global is untouched
        print(i)
```

### `[sugar.promotion]` DWIM promotion { #sugar-promotion }

A name implicitly assigned in every branch of a complete `if` chain is
promoted to the enclosing block. This must work, period, without the user
playing tricks.

```python
def f(x: i32) -> i32:
    if x < 0:
        y = -x
    else:
        y = x
    return y             # OK: promoted
```

Explicit equivalent:

```python
def f(x: i32) -> i32:
    var y: i32
    if x < 0:
        y = -x
    else:
        y = x
    return y
```

`elif` chains promote the same way:

```python
def f(n: i32) -> str:
    if n < 0:
        s = "neg"
    elif n == 0:
        s = "zero"
    else:
        s = "pos"
    return s             # OK
```

#### `[sugar.promotion-terminators]` Branches that cannot fall through are ignored { #sugar-promotion-terminators }

`return`, `raise`, `break` and `continue` end a branch, so it need not assign
the name.

```python
def f(cond: bool) -> i32:
    if cond:
        x = 1
    else:
        raise IndexError("nope")
    return x             # OK
```

```python
def f(cond: bool) -> i32:
    if cond:
        x = 1
    else:
        return 0
    return x             # OK
```

```python
def f() -> i32:
    for i in range(10):
        if i > 5:
            x = i
        else:
            continue
        return x         # OK
    return -1
```

A call that never returns is not recognized as a terminator:

```python
def f(cond: bool) -> i32:
    if cond:
        x = 1
    else:
        fatal("nope")    # fatal() -> NoReturn
    return x             # ERROR: `x` not in scope
```

#### `[sugar.promotion-incomplete]` An incomplete chain does not promote { #sugar-promotion-incomplete }

```python
def f(cond: bool) -> None:
    if cond:
        x = 1
    print(x)             # ERROR: `x` not in scope
```

#### `[sugar.promotion-transitive]` Promotion targets the enclosing block, and is transitive { #sugar-promotion-transitive }

```python
def f(a: bool, b: bool) -> None:
    if a:
        if b:
            x = 1
        else:
            x = 2
        print(x)         # OK: promoted to the `if a:` block
    print(x)             # ERROR: `x` not in scope here
```

```python
def f(a: bool, b: bool) -> i32:
    if a:
        if b:
            x = 1
        else:
            x = 2
    else:
        x = 3
    return x             # OK: promoted twice
```

#### `[sugar.promotion-opt-out]` Explicit declarations are never promoted { #sugar-promotion-opt-out }

This is how you opt out.

```python
def f(cond: bool) -> None:
    if cond:
        const x = 1
    else:
        const x = 2
    print(x)             # ERROR: branch-local
```

#### `[sugar.promotion-conflict]` A chain may not both declare and assign one name { #sugar-promotion-conflict }

If one fall-through branch declares a name explicitly and another assigns it,
that is an error: otherwise the code below would read like the promoting form
and behave like the opt-out. The error is reported on the chain itself,
whether or not `x` is used afterwards.

```python
def f(cond: bool) -> None:
    if cond:
        var x: i32 = 1   # ERROR: `x` is declared explicitly here...
    else:
        x = 2            #        ...and assigned here
```

It applies equally when the assignment reassigns an enclosing binding rather
than declaring a new one, since the two are indistinguishable at a glance:

```python
def f(cond: bool) -> None:
    var x: i32 = 0
    if cond:
        var x: i32 = 1   # ERROR: shadows here...
    else:
        x = 2            #        ...reassigns the outer x here
    print(x)
```

Either spelling is fine as long as the chain is consistent:

```python
def f(cond: bool) -> None:
    if cond:
        x = 1
    else:
        x = 2
    print(x)             # OK: all implicit → promoted
```

```python
def f(cond: bool) -> None:
    if cond:
        var x: i32 = 1
    else:
        var x: i32 = 2   # OK: all explicit → both branch-local
```

A name promoted into a branch from a nested chain counts as implicit, so it
does not clash with an implicit binding in a sibling branch.

A branch that cannot fall through is not part of the comparison:

```python
def f(cond: bool) -> i32:
    if cond:
        var x: i32 = 1
        return x
    else:
        x = 2
    return x             # OK: the then branch cannot fall through
```

#### `[sugar.promotion-loop]` Loop bodies never promote { #sugar-promotion-loop }

A loop runs 0..N times, so a name assigned only inside it is never definitely
assigned.

```python
def f() -> None:
    for i in range(10):
        total = i
    print(total)         # ERROR: `total` not in scope
```

#### `[sugar.promotion-types]` Every branch must assign the identical type { #sugar-promotion-types }

SPy never unifies branch types into a common supertype: that would be
behavior-changing and backend-divergent.

```python
def f(cond: bool) -> None:
    if cond:
        x = 1            # fixes x: i32
    else:
        x = 2.5          # ERROR: expected `i32`, got `f64`
    print(x)
```

Both orders are rejected:

```python
def f(cond: bool) -> None:
    if cond:
        p = Person()
    else:
        p = Student()    # ERROR: expected `Person`, got `Student`
    p.work()
```

```python
def f(cond: bool) -> None:
    if cond:
        p = Student()
    else:
        p = Person()     # ERROR: expected `Student`, got `Person`
    p.work()
```

The fix is to name the type you mean, and then the branches are ordinary
reassignments against a declared type
([`[decl.type-fixed]`](#decl-type-fixed)), so conversions apply:

```python
def f(cond: bool) -> None:
    var p: Person
    if cond:
        p = Person()
    else:
        p = Student()    # OK: Student <: Person
    p.work()             # non-virtual: Person.work, in every backend
```

```python
def f(cond: bool) -> None:
    var x: f64 = 0.0
    if cond:
        x = 1            # OK: i32 converts to the declared f64
    else:
        x = 2.5
    print(x)
```

The conflict is detected when both branches are compiled, so it is reported
by `-m doppler` and `-m C`, and not by `-m interp`, which executes only one
branch.

#### `[sugar.promotion-blue]` A blue test collapses the chain { #sugar-promotion-blue }

Only the taken branch is compiled, so there is no second type to compare.

```python
@blue
def f() -> None:
    if SOME_BLUE_FLAG:
        x = 1            # x: i32
    else:
        x = "hi"         # not compiled
    print(x)             # OK
```

#### `[sugar.promotion-const]` A promoted binding is `const` when every path assigns it once { #sugar-promotion-const }

So it stays blue under a blue test:

```python
TUP = 1, 2.5, "hello"
COND = True

@blue
def f() -> None:
    if COND:
        n = 0
    else:
        n = 1
    print(TUP[n])        # OK: const → blue
```

Under a red test the value depends on which branch ran, so it is red:

```python
def f(cond: bool) -> None:
    if cond:
        n = 0
    else:
        n = 1
    print(TUP[n])        # ERROR: tuple index must be blue
```

This applies only to promoted bindings: an ordinary block-local inside a
red-tested branch is still blue.

```python
def f(cond: bool) -> None:
    if cond:
        m = 0            # const → blue
        print(TUP[m])    # 1
```

#### `[sugar.promotion-unroll]` Promotion + blue-time loop unrolling { #sugar-promotion-unroll }

`item` is promoted to the loop body block, never to the function, so each
unrolled iteration gets its own binding with its own type.

```python
TUP = 1, 2.5, "hello"

def f() -> None:
    for i in unroll(range(3)):
        if i == 0:
            item = TUP[0]
        else:
            item = TUP[i]
        print(item)      # i32, then f64, then str
```

Roughly, after redshifting:

```python
def f() -> None:
    item$0 = 1
    print(item$0)
    item$1 = 2.5
    print(item$1)
    item$2 = "hello"
    print(item$2)
```

### `[sugar.shadow-write]` A bare assignment never targets an outer function or module { #sugar-shadow-write }

It binds locally even when the name is visible outside. Use `global` /
`nonlocal` to reach outward, the same rule as Python.

```python
var B: i32 = 2

def main() -> None:
    B = 0                # a new local B; the global is untouched
    print(B)             # 0
```

```python
def main() -> None:
    global B
    B = 0                # mutate the outer B
```

```python
A = 1                    # module-level const

def main() -> None:
    A = 0                # a new local A, shadowing the const
```

The same rule covers closures:

```python
def outer() -> None:
    var n: i32 = 0
    def inner() -> None:
        n = 1            # a new local n in inner
    def writer() -> None:
        nonlocal n
        n = 1            # mutates outer's n
```

### `[sugar.shadow-write-caught]` The read-then-write mistake is caught by use-before-declaration { #sugar-shadow-write-caught }

Forgetting `global` is the classic Python mistake. In its usual shape,
[`[decl.use-before]`](#decl-use-before) turns it into a static error.

```python
var COUNT: i32 = 0

def bump() -> None:
    COUNT = COUNT + 1    # ERROR: `COUNT` used before its declaration
```

A write-only shadow stays silent. We are aware of it and accept it for now;
real usage will tell us whether it deserves a diagnostic (see
[`[future.firewall]`](#future-firewall)).

```python
var COUNT: i32 = 0

def reset() -> None:
    COUNT = 0            # a dead local; the global is untouched
```

## Future directions

/// note | Not yet implemented
The rules in this section describe ideas under discussion. None of them are
implemented; they are documented here to give context for design decisions
made elsewhere in this page.
///

### `[future.definite-assignment]` Definite assignment { #future-definite-assignment }

Makes the current dynamic "read from uninitialized local" check static.

```python
def f(cond: bool) -> None:
    var x: i32
    if cond:
        x = 1
    print(x)             # ERROR: `x` may be uninitialized
```

### `[future.narrowing]` Type narrowing, read-side only { #future-narrowing }

The declared type never changes ([`[decl.type-fixed]`](#decl-type-fixed));
narrowing is a lens for reads.

```python
def f(x: i32 | str) -> None:
    if isinstance(x, i32):
        use_int(x)       # x reads as i32
    else:
        use_str(x)       # x reads as str
    print(x)             # x: i32 | str again
```

`assert` narrows to the end of the enclosing block:

```python
def f(x: i32 | None, cond: bool) -> None:
    if cond:
        assert x is not None
        print(x + 1)     # x: i32
    use(x)               # x: i32 | None
```

A write invalidates the narrowing:

```python
def f(x: i32 | str) -> None:
    if isinstance(x, i32):
        use_int(x)       # x: i32
        x = some()
        use(x)           # x: i32 | str
```

### `[future.rebind]` Same-scope rebinding, Rust style { #future-rebind }

Relaxes [`[decl.no-redeclare]`](#decl-no-redeclare).

```python
def f() -> None:
    var x: i32 = 1
    var x: str = "hi"    # OK under this rule: a fresh binding
```

### `[future.block-lifetime]` Block-local lifetime { #future-block-lifetime }

Block-locals currently stay reachable until the function returns; this rule
would make them die with their block, and let the C backend emit one `{ }`
per block.

```python
def f(cond: bool) -> None:
    if cond:
        var big = make_huge()
    # `big` would be collectable here, not at function exit
    do_other_work()
```

### `[future.firewall]` The firewall { #future-firewall }

Reject a bare assignment when the name is visible as a mutable `var` in an
outer function or module scope, instead of silently making a local
([`[sugar.shadow-write]`](#sugar-shadow-write)). Shadowing an outer `const`
would stay silent, since there is no mutable binding to hit by accident.

```python
var B: i32 = 2

def main() -> None:
    B = 0                # under this rule: ERROR - say `global B`, or `var B` for a local
```

It targets the one case [`[decl.use-before]`](#decl-use-before) cannot catch,
the write-only shadow:

```python
var COUNT: i32 = 0

def reset() -> None:
    COUNT = 0            # under this rule: ERROR instead of a silent dead local
```

Against it: name resolution would depend on the mutability of a binding in
another scope, and a function that legitimately wants a local named like a
mutable global would have to rename or declare it explicitly. A narrower
alternative is a warning when an implicit local shadows a visible outer name
*and is never read*, which is the accidental-global-write signature without
the false positives.
</content>
