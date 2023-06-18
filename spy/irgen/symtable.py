from typing import Optional
from dataclasses import dataclass
from spy.vm.object import W_Type, W_Object

class SymbolAlreadyDeclaredError(Exception):
    """
    A symbol is being redeclared
    """

@dataclass
class Symbol:
    name: str
    w_type: W_Type
    #w_constval: Optional[W_Object]


class SymTable:
    name: str  # just for debugging
    parent: Optional['SymTable']
    symbols: dict[str, Symbol]

    def __init__(self, name: str, *, parent: Optional['SymTable']) -> None:
        self.name = name
        self.parent = parent
        self.symbols = {}

    def declare(self, name: str, w_type: W_Type) -> Symbol:
        if name in self.symbols:
            raise SymbolAlreadyDeclaredError(name)
        self.symbols[name] = s = Symbol(name, w_type)
        return s

    def lookup(self, name: str) -> Optional[Symbol]:
        if name in self.symbols:
            # found in the local scope
            return self.symbols[name]
        elif self.parent is not None:
            return self.parent.lookup(name)
        else:
            return None # not found
