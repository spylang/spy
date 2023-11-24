from typing import Optional, Literal
from dataclasses import dataclass, KW_ONLY
from spy.ast import Color
from spy.fqn import FQN
from spy.location import Loc
from spy.errors import SPyScopeError
from spy.vm.vm import SPyVM, Builtins as B
from spy.vm.object import W_Type, W_Object

Qualifier = Literal['var', 'const']

class SymbolAlreadyDeclaredError(Exception):
    """
    A symbol is being redeclared

    XXX kill me
    """


@dataclass
class Symbol:
    name: str
    color: Color
    _: KW_ONLY
    loc: Loc           # where the symbol is defined, in the source code
    scope: 'SymTable'  # the scope where the symbol lives in
    fqn: Optional[FQN] = None
    #
    # only for legacy, will be killed soon
    qualifier: Optional[Qualifier] = None
    w_type: Optional[W_Type] = None



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
        res = cls('builtins', parent=None)
        loc = Loc(filename='<builtins>',
                  line_start=0,
                  line_end=0,
                  col_start=0,
                  col_end=0)
        #
        builtins_mod = vm.modules_w['builtins']
        for fqn, w_obj in builtins_mod.items_w():
            w_type = vm.dynamic_type(w_obj)
            # XXX kill declare_legacy and use declare
            res.declare_legacy(fqn.attr, 'const', w_type, loc, fqn=fqn,
                               color='blue')
        return res

    def __repr__(self) -> str:
        return f'<SymTable {self.name}>'

    def pp(self) -> None:
        print(f"<symbol table '{self.name}'>")
        for name, sym in self.symbols.items():
            assert name == sym.name
            print(f'    {name}: {sym.color}')

    def declare(self, name: str, color: Color, loc: Loc,
                fqn: Optional[FQN] = None) -> Symbol:
        prev_sym = self.lookup(name)
        if prev_sym:
            if prev_sym.scope is self:
                # re-declaration
                msg = f'variable `{name}` already declared'
            else:
                # shadowing
                msg = (f'variable `{name}` shadows a name declared ' +
                       "in an outer scope")
            err = SPyScopeError(msg)
            err.add('error', 'this is the new declaration', loc)
            err.add('note', 'this is the previous declaration', prev_sym.loc)
            raise err

        self.symbols[name] = s = Symbol(name = name,
                                        color = color,
                                        loc = loc,
                                        scope = self,
                                        fqn = fqn)
        return s

    def declare_legacy(self, name: str, qualifier: Qualifier, w_type: W_Type,
                       loc: Loc, fqn: Optional[FQN] = None,
                       color: Color = 'red') -> Symbol:
        if name in self.symbols:
            raise SymbolAlreadyDeclaredError(name)
        self.symbols[name] = s = Symbol(name = name,
                                        color = color,
                                        qualifier = qualifier,
                                        loc = loc,
                                        scope = self,
                                        fqn = fqn,
                                        w_type = w_type)
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
