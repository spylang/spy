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

from typing import Optional, Any, Union, Sequence
from dataclasses import dataclass
import re

PARTS = Sequence[Union[str, 'NSPart']]
QUALIFIERS = Optional[Sequence[Union[str, 'FQN']]]

def get_parts(x: PARTS) -> list['NSPart']:
    parts = []
    for part in x:
        if isinstance(part, str):
            parts.append(NSPart(part, []))
        elif isinstance(part, NSPart):
            parts.append(part)
        else:
            assert False
    return parts

def get_qualifiers(x: QUALIFIERS) -> list['FQN']:
    x = x or []
    quals = []
    for item in x:
        if isinstance(item, str):
            quals.append(FQN(item))
        elif isinstance(item, FQN):
            quals.append(item)
        else:
            assert False
    return quals

@dataclass
class NSPart:
    name: str
    qualifiers: list['FQN']
    suffix: int = 0

    def __init__(self, name: str, quals: QUALIFIERS=None, suffix: int=0) -> None:
        self.name = name
        self.qualifiers = get_qualifiers(quals)
        self.suffix = suffix

    def __str__(self) -> str:
        result = self.name
        if len(self.qualifiers) > 0:
            quals = ', '.join(q.human_name for q in self.qualifiers)
            result = f'{result}[{quals}]'
        if self.suffix != 0:
            result += f'#{self.suffix}'
        return result

    @property
    def c_name(self) -> str:
        name = self.name.replace('.', '_')
        result = name
        if len(self.qualifiers) > 0:
            quals = '_'.join(fqn.c_name_plain for fqn in self.qualifiers)
            result = f'{result}__{quals}'
        if self.suffix != 0:
            result += f'${self.suffix}'
        return result


class FQN:
    parts: list[NSPart]

    def __new__(cls, x: str | PARTS) -> 'FQN':
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

    def with_suffix(self, suffix: int) -> 'FQN':
        """
        Create a new FQN with the specified suffix on the last NSPart.
        """
        res = FQN(self.parts)
        res.parts[-1].suffix = suffix
        return res

    def with_qualifiers(self, qualifiers: QUALIFIERS) -> 'FQN':
        """
        Create a new FQN with the specified qualifiers added to the last NSPart.
        """
        new_parts = []
        for i, part in enumerate(self.parts):
            if i < len(self.parts) - 1:
                # For all parts except the last one, create a copy
                new_part = NSPart(part.name, part.qualifiers.copy(), part.suffix)
                new_parts.append(new_part)
            else:
                # For the last part, create a copy with the new qualifiers added
                new_quals = part.qualifiers.copy() + get_qualifiers(qualifiers)
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
        if human and str(parts[0]) == 'builtins':
            parts = parts[1:]
        s = '::'.join(str(part) for part in parts)
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
        is_def = (len(self.parts) == 2 and
                  self.modname == 'builtins' and
                  self.parts[1].name == 'def')
        if is_def:
            quals = [fqn.human_name for fqn in self.parts[1].qualifiers]
            p = ', '.join(quals[:-1])
            r = quals[-1]
            return f'def({p}) -> {r}'
        else:
            return self._fullname(human=True)

    @property
    def modname(self) -> str:
        return str(self.parts[0])

    @property
    def namespace(self) -> 'FQN':
        return FQN(self.parts[:-1])

    @property
    def symbol_name(self) -> str:
        return str(self.parts[-1])

    def join(self, name: str, qualifiers: QUALIFIERS=None) -> 'FQN':
        """
        Create a new FQN nested inside the current one.
        """
        qual2 = get_qualifiers(qualifiers)
        return FQN(self.parts + [NSPart(name, qual2)])

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
        return f'spy_{self.c_name_plain}'

    @property
    def c_name_plain(self) -> str:
        """
        Like c_name, but without the spy_ prefix
        """
        parts = [part.c_name for part in self.parts]
        cn = '$'.join(parts)
        return cn

    @property
    def spy_name(self) -> str:
        # this works only for very simple cases
        return '.'.join(part.name for part in self.parts)

    def is_module(self) -> bool:
        return len(self.parts) == 1

    def is_object(self) -> bool:
        return not self.is_module()
