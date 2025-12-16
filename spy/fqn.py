"""
Fully Qualified Names (FQN) in SPy.

An FQN uniquely identify functions, types and constants inside a running SPy
VM.

An FQN is composed by one or more Namespace Parts (NSPart), separated by '::'.
It can have an optional suffix, separated by '#'
    part0::part1::...
    part0::part1#2

An NSPart is composed by a name and an optional list of qualifiers:
    name
    name[q0, q1, ...]

NSPart.name can contain the following characters:
  - letters (a-z, A-Z)
  - digits (0-9)
  - underscore (_)
  - dot (.)

The list of qualifiers can contain zero or more FQNs.


Examples:

  - "foo": one unqualified part: "foo"
  - "mod::foo": two unqualified parts: "mod" and "foo"
  - "a.b.c::foo": two unqualified parts: "a.b.c" and "foo"
  - "foo#2": one unqualified part "foo", with suffix "2"
  - "list[i32]": one unqualified part "list" with a qualifier "i32"
  - "dict[str, unsafe::ptr[i32]]"


Various subparts of a FQN have different names:

  - the first part is the "module name", which usually corresponds to a single
    .spy file

  - the parts up to the last one are the "namespace"

  - the last part is the "symbol name"

E.g., for "builtins::list[i32]::append":
  - module name: "builtins"
  - namespace: "builtins::list[i32]"
  - symbol name: "append"


In case of closures you can have multiple objects with the same FQN. To
disambiguate, we append an unique suffix

@blue
def make_fn(T):
    def fn(x: T) -> T:
        # FQN is 'test::make_fn::fn'
        return ...
    return fn

fn_i32 = make_fn(i32)  # FQN is 'test::make_fn::fn#1'
fn_f64 = make_fn(f64)  # FQN is 'test::make_fn::fn#2'

See also vm.get_unique_FQN.
"""

import functools
import re
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence, Union

PARTS = Sequence[Union[str, "NSPart"]]
QUALIFIERS = Optional[Sequence[Union[str, "FQN"]]]


def get_parts(x: PARTS) -> tuple["NSPart", ...]:
    parts = []
    for part in x:
        if isinstance(part, str):
            parts.append(NSPart(part, ()))
        elif isinstance(part, NSPart):
            parts.append(part)
        else:
            assert False
    return tuple(parts)


def get_qualifiers(x: QUALIFIERS) -> tuple["FQN", ...]:
    x = x or ()
    quals = []
    for item in x:
        if isinstance(item, str):
            quals.append(FQN(item))
        elif isinstance(item, FQN):
            quals.append(item)
        else:
            assert False
    return tuple(quals)


@dataclass(frozen=True)
class NSPart:
    name: str
    qualifiers: tuple["FQN", ...]
    suffix: str = ""

    def __init__(self, name: str, quals: QUALIFIERS = None, suffix: str = "") -> None:
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "qualifiers", get_qualifiers(quals))
        object.__setattr__(self, "suffix", suffix)

    def __str__(self) -> str:
        result = self.name
        if len(self.qualifiers) > 0:
            quals = ", ".join(q.human_name for q in self.qualifiers)
            result = f"{result}[{quals}]"
        if self.suffix != "":
            result += f"#{self.suffix}"
        return result

    @property
    def c_name(self) -> str:
        name = self.name.replace(".", "_")
        result = name
        if len(self.qualifiers) > 0:
            quals = "_".join(fqn.c_name_plain for fqn in self.qualifiers)
            result = f"{result}__{quals}"
        if self.suffix != "":
            result += f"${self.suffix}"
        return result


class FQN:
    parts: tuple[NSPart, ...]

    def __new__(cls, x: str | PARTS) -> "FQN":
        """
        Supported overloads:
            FQN(x: str)
            FQN(x: PARTS)
        """
        from .fqn_parser import FQNParser

        if isinstance(x, str):
            return FQNParser(x).parse()
        else:
            fqn = super().__new__(cls)
            fqn.parts = get_parts(x)
            return fqn

    # uncomment this to understand who creates a specific FQN
    ## def __init__(self, *args) -> None:
    ##     if str(self) == 'test::Point#0':
    ##         breakpoint()

    def with_suffix(self, suffix: str) -> "FQN":
        """
        Create a new FQN with the specified suffix on the last NSPart.
        """
        new_parts = list(self.parts)
        last_part = new_parts[-1]
        new_parts[-1] = NSPart(last_part.name, last_part.qualifiers, suffix)
        return FQN(new_parts)

    def with_qualifiers(self, qualifiers: QUALIFIERS) -> "FQN":
        """
        Create a new FQN with the specified qualifiers added to the last NSPart.
        """
        new_parts = []
        for i, part in enumerate(self.parts):
            if i < len(self.parts) - 1:
                # For all parts except the last one, create a copy
                new_part = NSPart(part.name, part.qualifiers, part.suffix)
                new_parts.append(new_part)
            else:
                # For the last part, create a copy with the new qualifiers added
                new_quals = part.qualifiers + get_qualifiers(qualifiers)
                new_part = NSPart(part.name, new_quals, part.suffix)
                new_parts.append(new_part)

        res = FQN(new_parts)
        return res

    def __repr__(self) -> str:
        return f"FQN({self.fullname!r})"

    def __str__(self) -> str:
        return self.fullname

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, FQN):
            return NotImplemented
        return self.fullname == other.fullname

    def __hash__(self) -> int:
        return hash(self.fullname)

    def _fullname(self, human: bool) -> str:
        parts = self.parts
        if human and str(parts[0]) == "builtins":
            parts = parts[1:]
        s = "::".join(str(part) for part in parts)
        return s

    @property
    def fullname(self) -> str:
        return self._fullname(human=False)

    @property
    def human_name(self) -> str:
        """
        Like fullname, but doesn't show 'builtins::',
        and special-case 'def[...]'
        """
        is_def = (
            len(self.parts) == 2
            and self.modname == "builtins"
            and self.parts[1].name
            in (
                "def",
                "blue.def",
                "blue.generic.def",
                "blue.metafunc.def",
            )
        )
        if is_def:
            p1 = self.parts[1]
            if p1.name == "def":
                d = "def"
            elif p1.name == "blue.def":
                d = "@blue def"
            elif p1.name == "blue.generic.def":
                d = "@blue.generic def"
            elif p1.name == "blue.metafunc.def":
                d = "@blue.metafunc def"
            else:
                assert False
            quals = [fqn.human_name for fqn in p1.qualifiers]
            p = ", ".join(quals[:-1])
            r = quals[-1]
            if r == "types::NoneType":
                r = "None"
            return f"{d}({p}) -> {r}"

        is_varargs_param = (
            len(self.parts) == 2
            and self.modname == "builtins"
            and self.parts[1].name == "__varargs__"
        )
        if is_varargs_param:
            p1 = self.parts[1]
            assert len(p1.qualifiers) == 1
            q0 = p1.qualifiers[0]
            return f"*{q0.human_name}"

        return self._fullname(human=True)

    @property
    def modname(self) -> str:
        return str(self.parts[0])

    @property
    def namespace(self) -> "FQN":
        return FQN(self.parts[:-1])

    @property
    def symbol_name(self) -> str:
        return str(self.parts[-1])

    def join(self, name: str, qualifiers: QUALIFIERS = None) -> "FQN":
        """
        Create a new FQN nested inside the current one.
        """
        qual2 = get_qualifiers(qualifiers)
        return FQN(self.parts + (NSPart(name, qual2),))

    def parent(self) -> "FQN":
        return FQN(self.parts[:-1])

    @property
    def c_name(self) -> str:
        """
        Return the C name for the corresponding FQN.

        We need to do a bit of mangling:

          - the modname part can be dotted: we replace '.' with '_'. Note that
            this is potentially unsafe, because e.g. `a.b.c` and `a.b_c` would
            result in the same C name.  This is not ideal but we will solve it
            only if it becomes an actual issue in practice.

          - for separating parts, we use a '$'. Strictly speaking,
            using a '$' in C identifiers is not supported by the standard, but
            in reality it is supported by GCC, clang and MSVC. Again, we will
            think of a different approach if it becomes an actual issue.

          - if a part has qualifiers, we use '__' to separate the name from the
            qualifiers, and '_' to separate each qualifier. Same as above w.r.t.
            safety.

          - if the FQN has a suffix, we append it with a '$'.

        So e.g., the following FQN:
            mod::dict[i32, f64]::foo#0

        Becomes:
            spy_mod$dict__i32_f64$foo$0
        """
        return f"spy_{self.c_name_plain}"

    @property
    def c_name_plain(self) -> str:
        """
        Like c_name, but without the spy_ prefix
        """
        parts = [part.c_name for part in self.parts]
        cn = "$".join(parts)
        return cn

    @property
    def spy_name(self) -> str:
        # this works only for very simple cases
        return ".".join(part.name for part in self.parts)

    def is_module(self) -> bool:
        return len(self.parts) == 1

    def is_object(self) -> bool:
        return not self.is_module()

    def match(self, pattern: str) -> bool:
        """
        Check whether the string representation of the FQN matches the
        given pattern.

        pattern is *not* a regexp: the only character is '*' which matches any
        string.
        """
        r = _compile_pattern(pattern)
        return r.match(str(self))


@functools.lru_cache(maxsize=32768)
def _compile_pattern(pattern: str) -> Any:
    pattern = re.escape(pattern)
    regexp = pattern.replace(r"\*", ".*")
    return re.compile(regexp)
