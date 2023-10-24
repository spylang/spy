from typing import Optional, Literal
from dataclasses import dataclass, KW_ONLY
import spy.ast
from spy.location import Loc
from spy.vm.vm import SPyVM, Builtins as B
from spy.vm.object import W_Type, W_Object

Qualifier = Literal['var', 'const']

class SymbolAlreadyDeclaredError(Exception):
    """
    A symbol is being redeclared
    """


@dataclass
class Symbol:
    name: str
    qualifier: Qualifier
    w_type: W_Type
    _: KW_ONLY
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

    @classmethod
    def from_builtins(cls, vm: SPyVM) -> 'SymTable':
        res = cls('<builtins>', parent=None)
        loc = Loc(filename='<builtins>',
                  line_start=1,
                  line_end=1,
                  col_start=1,
                  col_end=1)
        #
        for varname, w_obj in B.__dict__.items():
            if not varname.startswith('w_'):
                continue
            assert isinstance(w_obj, W_Object)
            w_type = vm.dynamic_type(w_obj)
            res.declare(varname[2:], 'const', w_type, loc)
        return res

    def __repr__(self) -> str:
        return f'<SymTable {self.name}>'

    def pp(self) -> None:
        print(f'<symbol table for {self.name}>')
        for name, sym in self.symbols.items():
            assert name == sym.name
            print(f'    {name}: {sym.w_type.name}')

    def declare(self, name: str, qualifier: Qualifier, w_type: W_Type,
                loc: Loc) -> Symbol:
        if name in self.symbols:
            raise SymbolAlreadyDeclaredError(name)
        self.symbols[name] = s = Symbol(name = name,
                                        qualifier = qualifier,
                                        w_type = w_type,
                                        loc = loc,
                                        scope = self)
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
