from typing import Optional
from dataclasses import dataclass
import spy.ast
from spy.vm.object import W_Type, W_Object

class SymbolAlreadyDeclaredError(Exception):
    """
    A symbol is being redeclared
    """


@dataclass
class Symbol:
    name: str
    w_type: W_Type
    loc: spy.ast.Location  # where the symbol was defined

class SymTable:
    name: str  # just for debugging
    parent: Optional['SymTable']
    symbols: dict[str, Symbol]

    def __init__(self, name: str, *, parent: Optional['SymTable']) -> None:
        self.name = name
        self.parent = parent
        self.symbols = {}

    def declare(self, name: str, w_type: W_Type, loc: spy.ast.Location) -> Symbol:
        if name in self.symbols:
            raise SymbolAlreadyDeclaredError(name)
        self.symbols[name] = s = Symbol(name, w_type, loc)
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
