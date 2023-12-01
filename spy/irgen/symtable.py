from typing import Optional, Literal, TYPE_CHECKING, Any
from dataclasses import dataclass, KW_ONLY, replace
from spy.fqn import FQN
from spy.location import Loc
from spy.errors import SPyScopeError
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

Color = Literal["red", "blue"]

@dataclass
class Symbol:
    name: str
    color: Color
    _: KW_ONLY
    loc: Loc           # where the symbol is defined, in the source code
    fqn: Optional[FQN] = None

    def replace(self, **kwargs: Any) -> 'Symbol':
        return replace(self, **kwargs)

    @property
    def is_local(self) -> bool:
        # XXX this should be self.level == 0
        return self.fqn is None

class SymTable:
    name: str  # just for debugging
    _symbols: dict[str, Symbol]

    def __init__(self, name: str) -> None:
        self.name = name
        self._symbols = {}

    @classmethod
    def from_builtins(cls, vm: 'SPyVM') -> 'SymTable':
        scope = cls('builtins')
        loc = Loc(filename='<builtins>',
                  line_start=0,
                  line_end=0,
                  col_start=0,
                  col_end=0)
        builtins_mod = vm.modules_w['builtins']
        for fqn, w_obj in builtins_mod.items_w():
            scope._symbols[fqn.attr] = Symbol(fqn.attr, 'blue', loc=loc, fqn=fqn)
        return scope

    def __repr__(self) -> str:
        return f'<SymTable {self.name}>'

    def pp(self) -> None:
        print(f"<symbol table '{self.name}'>")
        for name, sym in self._symbols.items():
            assert name == sym.name
            print(f'    {name}: {sym.color}')

    def add(self, sym: Symbol) -> None:
        self._symbols[sym.name] = sym

    def lookup(self, name: str) -> Symbol:
        return self._symbols[name]

    def lookup_maybe(self, name: str) -> Optional[Symbol]:
        return self._symbols.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._symbols
