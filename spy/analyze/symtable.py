from typing import Optional, Literal, TYPE_CHECKING, Any
from dataclasses import dataclass, KW_ONLY, replace
from spy.fqn import FQN
from spy.location import Loc
from spy.textbuilder import ColorFormatter
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

Color = Literal["red", "blue"]

def maybe_blue(*colors: Color) -> Color:
    """
    Return 'blue' if all the given colors are blue, else 'red'
    """
    if set(colors) == {'blue'}:
        return 'blue'
    else:
        return 'red'


@dataclass
class Symbol:
    name: str
    color: Color
    _: KW_ONLY
    loc: Loc       # where the symbol is defined, in the source code
    type_loc: Loc  # loc of the TYPE of the symbols

    # level indicates in which scope the symbol resides:
    #   0: this Symbol is defined in the scope corresponding to
    #      the curreny SymTable (i.e., it's a "local variable")
    #   1: this is the most immediate outer scope
    #   2: the outer-outer, etc.
    #
    # E.g., for a module-level funcdef, we have three levels:
    #   * 0: local variables inside the funcdef
    #   * 1: module-level scope
    #   * 2: builtins
    level: int
    fqn: Optional[FQN] = None

    def replace(self, **kwargs: Any) -> 'Symbol':
        return replace(self, **kwargs)

    @property
    def is_local(self) -> bool:
        return self.level == 0

    @property
    def is_global(self) -> bool:
        return self.level != 0 and self.fqn is not None

class SymTable:
    """
    Collect all the names used in a given scope.

    Names can be of two kinds:

      - definition: names which are introduced by this scope; sym.level == 0

      - reference: a name which is defined by an outer scope, and referenced
        by this scope; sym.level > 0.

    SymTable also record the color of the frame which it corresponds to:

      - frames associated to red functions are RED

      - frames associated to blue functions are BLUE

      - frames associated to modules, classdefs, etc. are also BLUE
    """
    name: str  # just for debugging
    color: Color
    _symbols: dict[str, Symbol]

    def __init__(self, name: str, color: Color) -> None:
        self.name = name
        self.color = color
        self._symbols = {}

    @classmethod
    def from_builtins(cls, vm: 'SPyVM') -> 'SymTable':
        from spy.vm.function import W_BuiltinFunc
        scope = cls('builtins', 'blue')
        generic_loc = Loc(filename='<builtins>',
                          line_start=0,
                          line_end=0,
                          col_start=0,
                          col_end=0)
        builtins_mod = vm.modules_w['builtins']
        for fqn, w_obj in builtins_mod.items_w():
            if isinstance(w_obj, W_BuiltinFunc):
                loc = w_obj.def_loc
            else:
                loc = generic_loc
            sym = Symbol(fqn.symbol_name, 'blue', loc=loc, type_loc=loc,
                         level=0, fqn=fqn)
            scope.add(sym)
        return scope

    def __repr__(self) -> str:
        return f"<SymTable '{self.name}'>"

    def pp(self) -> None:
        color = ColorFormatter(use_colors=True)
        name = color.set('green', self.name)
        print(f"<symbol table '{name}'>")
        # sort symbols by:
        #   1. level
        #   2. color (blue, then red)
        #   3. name (@special names last)
        symbols = sorted(
            self._symbols.values(),
            key=lambda sym: (sym.level, sym.color, sym.name.replace('@', '~')),
        )
        for sym in symbols:
            sym_name = color.set(sym.color, f'{sym.name:10s}')
            fqn = ''
            if sym.fqn:
                fqn = f' => {sym.fqn}'
            print(f'    [{sym.level}] {sym.color:4s} {sym_name} {fqn}')

    def add(self, sym: Symbol) -> None:
        assert sym.name not in self._symbols
        self._symbols[sym.name] = sym

    def has_definition(self, name: str) -> bool:
        return name in self._symbols and self._symbols[name].is_local

    def lookup(self, name: str) -> Symbol:
        return self._symbols[name]

    def lookup_maybe(self, name: str) -> Optional[Symbol]:
        return self._symbols.get(name)

    def lookup_definition_maybe(self, name: str) -> Optional[Symbol]:
        """
        Like lookup_maybe, but find the symbol ONLY if it's a definition
        (i.e., if it's a local name).
        """
        sym = self._symbols.get(name)
        if sym and sym.is_local:
            return sym
        return None
