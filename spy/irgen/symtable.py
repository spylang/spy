from typing import Optional
from dataclasses import dataclass
import spy.ast
from spy.location import Loc
from spy.vm.object import W_Type, W_Object

class SymbolAlreadyDeclaredError(Exception):
    """
    A symbol is being redeclared
    """


@dataclass
class Symbol:
    name: str
    w_type: W_Type
    loc: Loc           # where the symbol is defined, in the source code
    scope: 'SymTable'  # the scope where the symbol lives in

class SymTable:
    name: str  # just for debugging
    parent: Optional['SymTable']
    symbols: dict[str, Symbol]

    def __init__(self, name: str, *, parent: Optional['SymTable']) -> None:
        self.name = name
        self.parent = parent
        self.symbols = {}

    def __repr__(self) -> str:
        return f'<SymTable {self.name}>'

    def pp(self) -> None:
        print(f'<symbol table for {self.name}>')
        for name, sym in self.symbols.items():
            assert name == sym.name
            print(f'    {name}: {sym.w_type.name}')

    def declare(self, name: str, w_type: W_Type, loc: Loc) -> Symbol:
        if name in self.symbols:
            raise SymbolAlreadyDeclaredError(name)
        self.symbols[name] = s = Symbol(name, w_type, loc, self)
        return s

    def lookup(self, name: str) -> Optional[Symbol]:
        if name in self.symbols:
            # found in the local scope
            return self.symbols[name]
        elif self.parent is not None:
            return self.parent.lookup(name)
        else:
            return None # not found

    def lookup_type(self, name: str) -> Optional[W_Type]:
        sym = self.lookup(name)
        if sym:
            return sym.w_type
        return None
