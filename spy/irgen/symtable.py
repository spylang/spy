from typing import Optional, Literal, TYPE_CHECKING
from dataclasses import dataclass, KW_ONLY
from spy.ast import Color
from spy.fqn import FQN
from spy.location import Loc
from spy.errors import SPyScopeError
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

@dataclass
class Symbol:
    name: str
    color: Color
    _: KW_ONLY
    loc: Loc           # where the symbol is defined, in the source code
    scope: 'SymTable'  # the scope where the symbol lives in
    fqn: Optional[FQN] = None


class SymTable:
    name: str  # just for debugging
    parent: Optional['SymTable']
    symbols: dict[str, Symbol]

    def __init__(self, name: str, *, parent: Optional['SymTable']) -> None:
        self.name = name
        self.parent = parent
        self.symbols = {}

    @classmethod
    def from_builtins(cls, vm: 'SPyVM') -> 'SymTable':
        scope = cls('builtins', parent=None)
        loc = Loc(filename='<builtins>',
                  line_start=0,
                  line_end=0,
                  col_start=0,
                  col_end=0)
        builtins_mod = vm.modules_w['builtins']
        for fqn, w_obj in builtins_mod.items_w():
            scope.symbols[fqn.attr] = Symbol(fqn.attr, 'blue', loc=loc, fqn=fqn,
                                             scope=scope)
        return scope

    def __repr__(self) -> str:
        return f'<SymTable {self.name}>'

    def pp(self) -> None:
        print(f"<symbol table '{self.name}'>")
        for name, sym in self.symbols.items():
            assert name == sym.name
            print(f'    {name}: {sym.color}')
