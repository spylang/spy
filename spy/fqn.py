"""
(Fully) Qualified Names in SPy.

A Qualified Name (QN) locates a function or class inside the source code.

A QN is composed by one or more Namespace Parts (NSPart), separated by '::'.
Examples:
  - builtins::i32
  - a.b.c::foo
  - builtins::list[i32]::append
  - unsafe::ptr[Point]::getfield[i32]

A NSPart must be a valid Python identifier, but it can also contain dots.
NSParts have 0 or more "qualifiers", expressed in square brackets.

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

from typing import Optional, Any
from dataclasses import dataclass
import re

_NSPART = re.compile(r"([a-zA-Z_][a-zA-Z0-9_\.]*)(?:\[([a-zA-Z0-9_,\s\[\]]*)\])?")

@dataclass
class NSPart:
    name: str
    qualifiers: list['NSPart']

    @classmethod
    def parse(cls, s: str) -> 'NSPart':
        m = _NSPART.fullmatch(s)
        if not m:
            raise ValueError(f'Invalid NSPart: {s}')
        name = m.group(1)
        qualifiers_str = m.group(2)
        qualifiers = cls.parse_qualifiers(qualifiers_str) if qualifiers_str else []
        return cls(name, qualifiers)

    @classmethod
    def parse_qualifiers(cls, s: str) -> list['NSPart']:
        qualifiers = []
        depth = 0
        start = 0
        for i, char in enumerate(s):
            if char == '[':
                depth += 1
            elif char == ']':
                depth -= 1
            elif char == ',' and depth == 0:
                qualifiers.append(cls.parse(s[start:i].strip()))
                start = i + 1
        if start < len(s):
            qualifiers.append(cls.parse(s[start:].strip()))
        return qualifiers

    def __str__(self) -> str:
        if len(self.qualifiers) == 0:
            return self.name
        else:
            quals = ', '.join(str(q) for q in self.qualifiers)
            return f'{self.name}[{quals}]'

    @property
    def c_name(self) -> str:
        name = self.name.replace('.', '_')
        if len(self.qualifiers) == 0:
            return name
        else:
            quals = '_'.join(q.c_name for q in self.qualifiers)
            return f'{name}__{quals}'

class QN:
    parts: list[NSPart]

    def __init__(self, x: str | list[str] | list[NSPart]) -> None:
        if isinstance(x, str):
            self.parts = self.parse(x)
        elif len(x) == 0:
            self.parts = []
        elif isinstance(x[0], NSPart):
            self.parts = x  # type: ignore
        else:
            self.parts = [NSPart.parse(part) for part in x]  # type: ignore

    @staticmethod
    def parse(s: str) -> list[NSPart]:
        parts = []
        for part in s.split("::"):
            parts.append(NSPart.parse(part))
        return parts

    def __repr__(self) -> str:
        return f"QN({self.fullname!r})"

    def __str__(self) -> str:
        return self.fullname

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, QN):
            return NotImplemented
        return self.fullname == other.fullname

    def __hash__(self) -> int:
        return hash(self.fullname)

    @property
    def fullname(self) -> str:
        return '::'.join(str(part) for part in self.parts)

    @property
    def modname(self) -> str:
        return str(self.parts[0])

    @property
    def namespace(self) -> 'QN':
        return QN(self.parts[:-1])

    @property
    def symbol_name(self) -> str:
        return str(self.parts[-1])

    def join(self, name: str) -> 'QN':
        """
        Create a new QN nested inside the current one.
        """
        return QN(self.parts + [NSPart.parse(name)])


class FQN:
    qn: QN
    suffix: str

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise ValueError("You cannot instantiate an FQN directly. "
                         "Please use vm.get_FQN()")

    @classmethod
    def make(cls, x: QN | str | list[str], *, suffix: str) -> 'FQN':
        obj = cls.__new__(cls)
        if isinstance(x, QN):
            obj.qn = x
        else:
            obj.qn = QN(x)
        obj.suffix = suffix
        return obj

    @classmethod
    def make_global(cls, x: QN | str | list[str]) -> 'FQN':
        """
        Return the FQN corresponding to a global name.
        """
        return cls.make(x, suffix="")

    @classmethod
    def parse(cls, s: str) -> 'FQN':
        if '#' in s:
            assert s.count('#') == 1
            s, suffix = s.split('#')
        else:
            suffix = ""
        #
        qn = QN(s)
        return FQN.make(qn, suffix=suffix)

    @property
    def fullname(self) -> str:
        s = self.qn.fullname
        if self.suffix != '':
            s += '#' + self.suffix
        return s

    @property
    def modname(self) -> str:
        return self.qn.modname

    @property
    def symbol_name(self) -> str:
        return self.qn.symbol_name

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
        parts = [part.c_name for part in self.qn.parts]
        cn = 'spy_' + '$'.join(parts)
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
