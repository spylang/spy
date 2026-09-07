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

We expect that Pythonic scoping rules are good enough for most daily usage, and most SPy
code will be written in that style.  The guidelines for the design are:

1. We aim to preserve Python semantics and/or Python "feeling" when possible.

2. It is fine to deviate from Python semantics if it makes the whole language better.

3. If we deviate from Python semantics, we should detect conflicting/ambiguous cases and
   report helpful error messages to guide the user towards the equivalent SPy form.

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
[`[py.constness]`](#py-constness).

If `TYPE` is `auto` or omitted, the type is inferred, see
[`[decl.auto]`](#decl-auto).

`initializer` can be omitted.

The following are valid declarations:
```python
def f() -> None:
    var a: int = 42    # full form
    const b: int = 43  # cannot be re-assigned
    var c: int         # will be initialized later
    const d: int       # same (only 1 assignment permitted)
    var e: auto = 44   # inferred type
    var f = 45         # same as above
    var g: auto        # same as above, will be initialized later
```

### `[decl.no-redeclare]` No re-declaration in the same scope { #decl-no-redeclare }

```python
def f() -> None:
    var x: i32 = 0
    var x: i32 = 1       # ERROR: `x` already declared
```

### `[decl.initializer]` The initializer may be omitted { #decl-initializer }

```python
def f() -> None:
    var x: i32
    x = 1
    print(x)             # 1
```

With the current rules, it might happen to read an uninitialized variable:
```python
def f() -> None:
    var x: i32
    if False:
        x = 42
    print(x)             # runtime error / UB: `x` may be unassigned
```

This error is caught at runtime by the interpreter, and results in UB in compiled mode.
This is a temporary limitation of SPy. Eventually we will implement
[`[future.definite-assignment]`](#future-definite-assignment).


### `[decl.auto]` Rules for `auto` type inference { #decl-auto }

`auto` implements a very limited form of type inference, by looking at the type of the
initializer:

```python
def f() -> None:
    const x: auto = 42  # i32
    const y = "hello"   # str
```

By design, SPy doesn't do whole-function or whole-program type inference. This is needed
to support the "fully interpreted" case, in which we execute things line by line:

```python
def f() -> None:
    var x: object = 42
    x = "hello"         # OK

    var y: auto = 42    # infers i32
    y = "hello"         # ERROR: expected `i32`, got `str`
```

If the initializer is omitted, the type is fixed on the **first assignment**:

```python
def f(cond: bool) -> None:
    var x: auto
    x = 1               # fixes x: i32
    x = "hello"         # ERROR: expected `i32`, got `str`
```

### `[decl.auto-unification]` Branches must assign the same type { #decl-auto-unification }

Uninitialized `auto` variables pose a problem in case the first assignment is executed
inside a conditional:

```python
def f(cond: bool) -> None:
    var x: auto
    if cond:
        x = 1
    else:
        x = "hello"
    print(STATIC_TYPE(x))    # works in interp, ERROR in compiler
```

We have multiple goals and implementation constraints:

  1. we would like to check that the type of `x` is the same in both branches and emit
     an error if they don't match.

  2. we would like that the *SPy interpreter* and the *SPy compiler* produce the exact
     same behavior.

The problem is that the interpreter only sees the branch which is actually taken, never
sees the other and thus it cannot possibly do the check.  **The unification check is
done only when compiling**.

This means that the snippet above prints either `i32` or `str` in `interp` mode, and
raises a compile time error in the other cases.  **This is one of the very few known
cases in which compiled code behaves differently than the interpreter**.

As a partial mitigation, we impose the rule that the type must be **exactly the same**
in all branches: we never try to find a common supertype. This way, we guarantee that
**if compilation succeeds, the behavior is exactly the same as in the interpreter**.

Consider this case:

```python
def f(cond: bool) -> f64:
    var x: auto
    if cond:
        x = 1      # i32
    else:
        x = 2.5    # f64
    return x
```

This fails because the inferred type is not an exact match in the two branches.  The fix
is to name the type you mean, and then the branches are ordinary reassignments against a
declared type, so conversions apply:

```python
def f(cond: bool) -> f64:
    var x: f64 = 0.0
    if cond:
        x = 1            # OK: implicit i32->f64 conversion
    else:
        x = 2.5
    return x
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
const A: i32 = 1

def main(cond: bool) -> None:
    if cond:
        print(A)         # ERROR: `A` is declared later in this function
    var A: i32 = 0
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

The same holds for loop bodies:

```python
def f() -> None:
    var x: i32 = 1
    for i in range(3):
        var x: i32 = i * 10
        print(x)         # 0, 10, 20
    print(x)             # 1
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


### `[scope.loop-target]` A loop target dies with its block { #scope-loop-target }

```python
def f() -> None:
    for i in range(10):
        pass
    print(i)             # ERROR: `i` is local to the `for` body
                         #        help: declare `var i: auto` before the loop
```

The next loop may therefore reuse the name at a different type.

```python
def f() -> None:
    for i in [1, 2, 3]:
        print(i)         # i: i32
    for i in ["a", "b"]:
        print(i)         # i: str, a different binding
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
[`[decl.initializer]`](#decl-initializer).

### `[scope.loop-fresh]` A block-local is fresh on each loop iteration { #scope-loop-fresh }

```python
def f() -> None:
    for i in range(3):
        var x: i32
        if i == 0:
            x = 1
        print(x)         # when i == 1: `x` is unassigned
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

### `[global.write]` Writing to a global needs `global` { #global-write }

A function can read a module-level name freely, but assigning to it requires
the `global` declaration, and the binding must be a `var`:

```python
from __spy__ import strict_scoping

var x: i32 = 42
var y: i32 = 43

def f() -> None:
    print(x)             # OK: read
    y = 0                # ERROR: `y` is not declared; say `global y`

def g() -> None:
    global x
    x = 0                # OK: mutates the global
```

`global` only re-targets the assignment; it does not grant mutability, so a
`const` global cannot be modified:

```python
const A = 1

def main() -> None:
    global A
    A = 0                # ERROR: `A` is a const (help: declare it `var A`)
```

### `[closure.nonlocal]` Closures read outer names freely; writing needs `nonlocal` { #closure-nonlocal }

This works like `global`, but for closures:
```python
from __spy__ import strict_scoping

def outer() -> None:
    var x: i32 = 0
    const y: i32 = 1
    def inner() -> None:
        print(x)         # OK: read capture
    def bad() -> None:
        x = 1            # ERROR: `x` is not declared; say `nonlocal x`
    def good() -> None:
        nonlocal x, y
        x = 1            # OK
        y = 1            # ERROR: `y` is a const (help: declare it `var y`)
```

Like `global`, `nonlocal` only re-targets the assignment; it does not grant
mutability (see [`[global.write]`](#global-write)).

### `[class.flat-body]` Class bodies are not blocks { #class-flat-body }

Field declarations bind in the class scope whatever their nesting.

```python
@struct
class P:
    x: i32
    if COND:
        y: i32           # OK: still a field of P
```


## Part 2 - Pythonic scoping

Sugar over strict scoping: every rule below has an explicit equivalent, and
`from __spy__ import strict_scoping` removes it.

### `[py.implicit-decl]` Implicit declaration on the first assignment { #py-implicit-decl }

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

### `[py.constness]` `var` / `const` is inferred from the number of assignments { #py-constness }

Not to be confused with mutability of values: this is about whether the *name* is
rebound, not whether the object it refers to can be mutated.  Assigned once → `const`;
assigned more than once → `var`.

```python
def f() -> None:
    a = 1                # const
    b = 1                # var
    b = b + 1
    c = 1                # var
    c += 1
```

The same inference applies to a declaration that has a type but no modifier (see
[`[decl.forms]`](#decl-forms)):

```python
def f() -> None:
    a: i32 = 1           # const
    b: i32 = 1           # var
    b = b + 1
```

### `[py.constness-paths]` The count is per execution path { #py-constness-paths }

A statement sequence sums; an `if` chain takes the max over its branches.

```python
def f(cond: bool) -> None:
    n: auto
    if cond:
        n = 0            # one assignment on either path → const
    else:
        n = 1
```

```python
def f(cond: bool) -> None:
    n: auto
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
    x: i32               # zero
    if cond:
        x = 1            # one on this path
```

An assignment inside a loop counts as multiple assignments, since the loop may
run more than once. A name declared outside the loop and assigned inside it is
therefore `var`:

```python
def f() -> None:
    n: auto
    for i in range(3):
        n = i            # inside a loop → counts as multiple → var
```

### `[py.walrus]` A walrus binds in the enclosing block { #py-walrus }

```python
def main() -> None:
    if (x := 5) > 0:
        print(x)         # 5
    print(x)             # OK: x lives in the function block
```

```python
def f() -> None:
    while (n := next_one()) > 0:
        print(n)
    print(n)             # OK: n lives in the function block
```


### `[py.blue-params]` Blue parameters are always `const` { #py-blue-params }

```python
@blue
def h(x: i32) -> None:
    x = x + 1            # ERROR: blue function arguments are const by default
```

### `[py.global-const-by-default]` Module level is `const` by default { #py-global-const-by-default }

```python
A = 1                    # const
var B: i32 = 2           # var
```

```python
A = 1
A = 2                    # ERROR: `A` already declared
```

### `[py.augassign]` `AugAssign` needs an existing binding { #py-augassign }

```python
def f() -> None:
    x += 1               # ERROR: name `x` is not defined
```

### `[py.def-class]` A nested `def` or `class` is a binding like any other { #py-def-class }

There is no special case: it follows the same rules as other assignments, so
it is block-local, and eligible for scope lifting
([`[py.scope-lifting]`](#py-scope-lifting)).

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
    print(g())           # OK: lifted
```


### `[py.scope-lifting]` Automatic scope lifting { #py-scope-lifting }

A name implicitly assigned anywhere inside an `if`/`elif`/`else` chain is
lifted to the enclosing block - unconditionally, regardless of whether every
branch assigns it and whether the chain has an `else` at all. The basic idea
is that something like this should work "out of the box":

```python
def f(x: i32) -> i32:
    if x < 0:
        y = -x
    else:
        y = x
    return y             # OK: lifted
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

`elif` chains lift the same way. Nesting is not special: each `if` applies
the same rule, so a name lifted out of an inner chain is just an ordinary
implicit assignment as far as the outer chain is concerned, and it lifts
again if the outer chain also assigns it on every spelled-out branch:

```python
def f(a: bool, b: bool) -> i32:
    if a:
        if b:
            x = 1
        else:
            x = 2
    else:
        x = 3
    return x             # OK: lifted twice
```

#### `[py.scope-lifting-partial]` Lifting does not check that every branch assigns { #py-scope-lifting-partial }

At this stage, we opt for a very simple rule: implicit declarations made inside an `if`
are always lifted.  Reading a name that turns out not to have been assigned on the
branch actually taken carries the same risk as reading an uninitialized explicit
declaration (see [`[decl.initializer]`](#decl-initializer)):

```python
def f(cond: bool) -> None:
    if cond:
        x = 1
    print(x)             # OK: lifted; runtime error / UB if `cond` is False
```

Is equivalent to:
```python
def f(cond: bool) -> None:
    cond: auto           # implicit lifting
    if cond:
        x = 1
    print(x)
```

[`[future.definite-assignment]`](#future-definite-assignment) describes how
this could eventually become a static error instead.

#### `[py.scope-lifting-opt-out]` Explicit declarations are never lifted { #py-scope-lifting-opt-out }

This is how you opt out.

```python
def f(cond: bool) -> None:
    if cond:
        const x = 1
    else:
        const x = 2
    print(x)             # ERROR: branch-local
```

A chain may not mix spellings for the same name: if one branch declares it explicitly
and another implicitly, that is an error:

```python
def f(cond: bool) -> None:
    if cond:
        var x: i32 = 1   # ERROR: `x` is declared explicitly here...
    else:
        x = 2            #        ...and implicitly here
```

A name lifted into a branch from a nested chain counts as implicit for this
check, so it does not clash with a bare assignment in a sibling branch:

```python
def f(a: bool, b: bool) -> None:
    if a:
        if b:
            x = 1
        else:
            x = 2        # `x` lifted here, still counts as implicit
    else:
        x = 3            # OK: also implicit, no conflict
    print(x)
```

Name lifting never crosses loop boundaries:
```python
def f() -> None:
    for i in range(10):
        if i > 5:
            x = 5
    print(x)            # ERROR: `x` is not declared
```

#### `[py.scope-lifting-loop]` Loop bodies never lift { #py-scope-lifting-loop }

Unlike `if`, a loop body must stay its own scope even when a name is
assigned on every iteration. [Blue-time
unrolling](#py-scope-lifting-unroll) relies on each iteration getting its
own fresh binding, potentially with its own type; lifting loop bodies the
way `if` does would collapse that into a single binding and break
unrolling.

```python
def f() -> None:
    for i in range(10):
        total = i
    print(total)         # ERROR: `total` not in scope
```

#### `[py.scope-lifting-blue]` A blue test collapses the chain { #py-scope-lifting-blue }

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

#### `[py.scope-lifting-const]` A lifted binding is `const` when every path assigns it once { #py-scope-lifting-const }

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

This applies only to lifted bindings: an ordinary block-local inside a
red-tested branch is still blue.

```python
def f(cond: bool) -> None:
    if cond:
        m = 0            # const → blue
        print(TUP[m])    # 1
```

#### `[py.scope-lifting-unroll]` Scope lifting + blue-time loop unrolling { #py-scope-lifting-unroll }

`item` is lifted to the loop body block, never to the function, so each
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

### `[py.shadow-write]` A bare assignment never targets an outer function or module { #py-shadow-write }

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

### `[py.shadow-write-caught]` The read-then-write mistake is caught by use-before-declaration { #py-shadow-write-caught }

Forgetting `global` is the classic Python mistake. In its usual shape,
[`[decl.use-before]`](#decl-use-before) turns it into a static error.

```python
var COUNT: i32 = 0

def bump() -> None:
    COUNT = COUNT + 1    # ERROR: `COUNT` used before its declaration
```

A write-only shadow stays silent. We are aware of it and accept it for now;
real usage will tell us whether it deserves a diagnostic (see
[`[future.shadow-guard]`](#future-shadow-guard)).

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

Makes the current dynamic "read from uninitialized local" check static, for
both explicit declarations and lifted implicit ones. This is likely the
first item from this section we implement, since it directly tightens
[`[py.scope-lifting]`](#py-scope-lifting).

For an explicit declaration:

```python
def f(cond: bool) -> None:
    var x: i32
    if cond:
        x = 1
    print(x)             # ERROR: `x` may be uninitialized
```

For a lifted name (see
[`[py.scope-lifting-partial]`](#py-scope-lifting-partial)), the same
analysis would reject the possibly-unassigned case statically instead of
accepting it with a runtime/UB risk:

```python
def f(cond: bool) -> None:
    if cond:
        x = 1
    print(x)             # under this rule: ERROR, `x` may be uninitialized
```

Once the analysis exists, it is natural to use it to make scope lifting
*checked* rather than purely syntactic: `return`, `raise`, `break` and
`continue` would end a branch, so it would not need to assign the name (a
call that never returns would still not count, since `NoReturn` is not
tracked):

```python
def f(cond: bool) -> i32:
    if cond:
        x = 1
    else:
        raise IndexError("nope")
    return x             # OK: `x` is definitely assigned
```

### `[future.narrowing]` Type narrowing, read-side only { #future-narrowing }

The declared type never changes; narrowing is a lens for reads.

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

### `[future.shadow-guard]` The shadow guard { #future-shadow-guard }

Reject a bare assignment when the name is visible as a mutable `var` in an
outer function or module scope, instead of silently making a local
([`[py.shadow-write]`](#py-shadow-write)). Shadowing an outer `const`
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
