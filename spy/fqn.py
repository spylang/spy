"""
(Fully) Qualified Names in SPy.

A Qualified Name (QN) locates a function or class inside the source code.

A QN is composed by one or more Namespace Parts (NSPart), separated by '::'.

NSPart.name can contain the following characters:
  - letters (a-z, A-Z)
  - digits (0-9)
  - underscore (_)
  - dot

NSPart can have a list of qualifiers. If the list is non-empty, the qualifiers
are expressed into square brackets, separated by commas.

Examples:

  - "foo": a QN composed by a single unqualified part
  - "mod::foo": a QN composed by two parts, "mod" and "foo"
  - "a.b.c::foo": a QN composed by two parts, "a.b.c" and "foo"
  - "list[i32]": a QN composed by a single part "list" with a qualifier "i32"
  - "dict[str, unsafe::ptr[i32]]"


Various subparts of a QN have different names:

  - the first part is the "module name", which usually corresponds to a single
    .spy file

  - the parts up to the last one are the "namespace"

  - the last part is the "symbol name"

E.g., for "builtins::list[i32]::append":
  - module name: "builtins"
  - namespace: "builtins::list[i32]"
  - symbol name: "append"


In case of closures and generics, you can have multiple objects with the same
QN. To uniquely identify an object inside a live VM, we use a Fully Qualified
Name, or FQN.  If needed, the uniqueness is guaranteed by appending a suffix,
represented as "#N". The suffix "" (empty string) is special cased and not shown
at all.

The following example explains the difference between QNs and FQNs:

@blue
def make_fn(T):
    def fn(x: T) -> T:
        # QN is 'test::fn' return ...
    return fn

fn_i32 = make_fn(i32)  # QN is 'test::make_fn::fn', FQN is 'test::make_fn::fn#1'
fn_f64 = make_fn(f64)  # QN is 'test::make_fn::fn', FQN is 'test::make_fn::fn#2'

See also SPyVM.get_FQN().
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

    def __init__(self, name: str, quals: QUALIFIERS=None) -> None:
        self.name = name
        self.qualifiers = get_qualifiers(quals)

    def __str__(self) -> str:
        if len(self.qualifiers) == 0:
            return self.name
        else:
            quals = ', '.join(q.human_name for q in self.qualifiers)
            return f'{self.name}[{quals}]'

    @property
    def c_name(self) -> str:
        name = self.name.replace('.', '_')
        if len(self.qualifiers) == 0:
            return name
        else:
            quals = '_'.join(fqn.c_name_plain for fqn in self.qualifiers)
            return f'{name}__{quals}'


class FQN:
    parts: list[NSPart]
    suffix: str

    def __init__(self, x: str | PARTS) -> None:
        if isinstance(x, str):
            fqn = FQN.parse(x)
            self.parts = fqn.parts[:]
        else:
            self.parts = get_parts(x)
        self.suffix = '' # ???


    @classmethod
    def make(cls, x: Union['FQN', str, list[str]], *, suffix: str) -> 'FQN':
        obj = cls.__new__(cls)
        obj.__init__(x)
        obj.suffix = suffix
        return obj

    @classmethod
    def make_global(cls, x: Union['FQN', str, list[str]]) -> 'FQN':
        """
        Return the FQN corresponding to a global name.
        """
        return cls.make(x, suffix='')

    @classmethod
    def parse(cls, s: str) -> 'FQN':
        from .fqn_parser import FQNParser
        fqn = FQNParser(s).parse()
        return fqn

    @property
    def qn(self) -> 'QN':
        # XXX KILL ME
        return self

    def with_suffix(self, suffix: str) -> 'FQN':
        res = FQN(self.parts)
        res.suffix = suffix
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

        if self.suffix != '':
            s += f'#{self.suffix}'
        return s

    @property
    def fullname(self) -> str:
        return self._fullname(human=False)

    @property
    def human_name(self) -> str:
        """
        Like fullname, but doesn't show 'builtins::'
        """
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
        parts = [part.c_name for part in self.qn.parts]
        cn = '$'.join(parts)
        if self.suffix != '':
            cn += '$' + self.suffix
        return cn

    @property
    def spy_name(self) -> str:
        # this works only for very simple cases
        return '.'.join(part.name for part in self.qn.parts)

    def is_module(self) -> bool:
        return len(self.qn.parts) == 1

    def is_object(self) -> bool:
        return not self.is_module()
