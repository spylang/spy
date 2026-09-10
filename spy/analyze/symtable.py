# ================== IMPORTANT: .spyc versioning =================
# Update importing.SPYC_VERSION in case of any significant change
# ================================================================

import pprint
from dataclasses import KW_ONLY, dataclass, replace
from typing import Any, Literal, Optional

from spy.location import Loc
from spy.textbuilder import ColorFormatter

# ====== VarKind rules ======
#
# Symbol.varkind determine whether a symbol is "var" or "const".
# Symbol.varkind_origin tracks how we determined the varkind.
#
# The varkind_origin can be "explicit":
#     var x: i32 = 0
#     const y: i32 = 0
#
# In all the other cases, it's determined by the context.
#
# Function and class definitions are always "const".
# Field definition inside a "class" are always "var".
# Function parameters are always "var".
#
# Module level assignments are "const" by default, unless explicitly marked as "var".
#
# Local variables inside a function follow these rules:
#   - if a variable is assigned only once, it's a "const"
#   - if a variable is assigned multiple times, it's a "var"
#   - if a variable is assigned inside a loop, it's a "var"

Color = Literal["red", "blue"]
VarStorage = Literal["direct", "cell", "NameError", "UnboundLocalError"]
VarKind = Literal["var", "const"]
VarKindOrigin = Literal[
    "auto",          # "x = 0" inside a function
    "global-const",  # "x = 0" at module level
    "explicit",      # "var x = 0" or "const x = 0"
    "funcdef",       # function defs are always "const"
    "classdef",      # class defs are always "const"
    "class-field",   # class field declarations are always "var"
    "red-param",     # parameters of red functions are "var"
    "blue-param",    # parameters of blue functions are "const"
]  # fmt: skip

# "module", "class", "function" each correspond to a different Frame for evaluation.
# "block" is used for if/for/while bodies: analysis-only, never a runtime frame.
ScopeKind = Literal["module", "class", "function", "block"]


def maybe_blue(*colors: Color) -> Color:
    """
    Return 'blue' if all the given colors are blue, else 'red'
    """
    if set(colors) == {"blue"}:
        return "blue"
    else:
        return "red"


@dataclass(frozen=True)
class ImportRef:
    """
    Represent a reference to an imported name.

    modname is a dotted string which identifies a module

    attr is the name of the attribute
    If attr is None, then the ImportRef references the whole module.

    E.g. 'a.b.c':
      modname: 'a.b'
      attr: 'c'
    """

    modname: str
    attr: Optional[str]

    def spy_name(self) -> str:
        modname = self.modname
        if "." in modname:
            modname = f"({modname})"
        if self.attr is None:
            return modname
        else:
            return f"{modname}.{self.attr}"

    def __repr__(self) -> str:
        n = self.spy_name()
        return f"<ImportRef {n}>"


@dataclass(frozen=True)
class Symbol:
    # ==== src_name vs slot_name ====
    #
    # - src_name is what is written in the source code, and what is displayed in
    #   diagnostic messages. A Scope is a collection of symbols indexed by src_name
    #
    # - slot_name is used at runtime to identify a local variable in the running
    #   ASTFrame. A SymTable is a collection of symbols indexed by slot_name.
    #
    # For example:
    #     def foo() -> None:
    #         const x = 0
    #         if 1:
    #             const x = 1
    #
    # Here we have two local vars: they both have src_name == "x", but their slot_names
    # are e.g. "x$0" and "x$1".
    src_name: str
    varkind: VarKind
    varkind_origin: VarKindOrigin
    storage: VarStorage
    _: KW_ONLY
    slot_name: str
    loc: Loc  # where the symbol is defined, in the source code
    type_loc: Loc  # loc of the TYPE of the symbols

    # level indicates in which scope the symbol resides:
    #   0: this Symbol is defined in the scope corresponding to
    #      the current SymTable (i.e., it's a "local variable")
    #   1: this is the most immediate outer scope
    #   2: the outer-outer, etc.
    #
    # E.g., for a module-level funcdef, we have three levels:
    #   * 0: local variables inside the funcdef
    #   * 1: module-level scope
    #   * 2: builtins
    level: int  # TODO: rename to frame_depth
    impref: Optional[ImportRef] = None

    def replace(self, **kwargs: Any) -> "Symbol":
        return replace(self, **kwargs)

    @property
    def is_local(self) -> bool:
        return self.level == 0

    def pp(self) -> None:
        pprint.pprint(self)


class Scope:
    """
    A lexical scope, as seen by the ScopeAnalyzer (scope2.py) during the bind
    and resolve passes.  Scopes are nested and correspond to a lexical region
    (function, module, block).

    A Scope is an ANALYSIS-ONLY concept: it is created by ScopeAnalyzer and
    discarded afterwards.
    """

    name: str
    color: Color
    kind: ScopeKind
    _symbols: dict[str, Symbol]

    def __init__(self, name: str, color: Color, kind: ScopeKind) -> None:
        self.name = name
        self.color = color
        self.kind = kind
        self._symbols = {}

    @classmethod
    def from_builtins(cls) -> "Scope":
        from spy.vm.b import BUILTINS
        from spy.vm.function import W_BuiltinFunc

        scope = cls("builtins", "blue", "module")
        generic_loc = Loc(
            filename="<builtins>", line_start=0, line_end=0, col_start=0, col_end=0
        )

        def add_sym(attr: str, impref: ImportRef, loc: Optional[Loc] = None) -> None:
            sym = Symbol(
                attr,
                "const",
                "explicit",
                "direct",
                slot_name=attr,
                loc=loc or generic_loc,
                type_loc=loc or generic_loc,
                level=0,
                impref=impref,
            )
            scope.add(sym)

        for fqn, w_obj, _irtag in BUILTINS.content:
            # add only top-level symbols
            if len(fqn.parts) != 2:
                continue
            attr = fqn.symbol_name
            loc = w_obj.def_loc if isinstance(w_obj, W_BuiltinFunc) else None
            add_sym(attr, ImportRef("builtins", attr), loc)

        add_sym("abs", ImportRef("_builtins", "abs"))
        add_sym("min", ImportRef("_builtins", "min"))
        add_sym("max", ImportRef("_builtins", "max"))
        add_sym("range", ImportRef("_range", "range"))
        add_sym("list", ImportRef("_list", "list"))
        add_sym("tuple", ImportRef("_tuple", "tuple"))
        add_sym("slice", ImportRef("_slice", "Slice"))
        add_sym("dict", ImportRef("_dict", "dict"))
        add_sym("file", ImportRef("_file", "file"))
        add_sym("open", ImportRef("_file", "open"))
        return scope

    def __repr__(self) -> str:
        return f"<Scope '{self.name}' ({self.color}, {self.kind})>"

    @property
    def depth(self) -> int:
        """
        Return the nesting depth of this scope (number of '::' separators).
        """
        return self.name.count("::")

    def pp(self, indent: str = "") -> None:
        pp_symbols(repr(self), self._symbols, indent)

    def add(self, sym: Symbol) -> None:
        # NOTE: we use src_name as the key (compare and contrast with SymTable.add)
        assert sym.src_name not in self._symbols
        self._symbols[sym.src_name] = sym

    def lookup_maybe(self, name: str) -> Optional[Symbol]:
        return self._symbols.get(name)


class SymTable:
    """
    A flat, per-frame runtime namespace.  It is attached to a FuncDef/ClassDef/
    Module and used at runtime by the frames to index their locals. It contains the
    definition of all the "local variables" of a given frame.

    SymTable also record the color of the frame which it corresponds to:

      - frames associated to red functions are RED

      - frames associated to blue functions are BLUE

      - frames associated to modules, classdefs, etc. are also BLUE

    NOTE: the legacy scope.py analyzer uses SymTable ALSO as its lexical scope
    (it predates the Scope class).  A few methods/fields below exist only to
    serve scope.py and should be removed once scope.py is gone; they are marked
    with "KILL ME".
    """

    name: str  # just for debugging
    color: Color
    kind: ScopeKind
    _symbols: dict[str, Symbol]
    implicit_imports: set[str]

    def __init__(self, name: str, color: Color, kind: ScopeKind) -> None:
        self.name = name
        self.color = color
        self.kind = kind
        self._symbols = {}
        self.implicit_imports = set()

    @classmethod
    def from_builtins(cls) -> "SymTable":
        # XXX: we should consider killing this once scope.py is gone
        builtins_scope = Scope.from_builtins()
        symtable = cls(builtins_scope.name, builtins_scope.color, builtins_scope.kind)
        symtable._symbols = dict(builtins_scope._symbols)
        return symtable

    def __repr__(self) -> str:
        return f"<SymTable '{self.name}' ({self.color}, {self.kind})>"

    @property
    def depth(self) -> int:
        """
        KILL ME: Return the nesting depth (number of '::' separators).
        """
        return self.name.count("::")

    def pp(self, indent: str = "") -> None:
        pp_symbols(repr(self), self._symbols, indent)

    def copy(self) -> "SymTable":
        new_st = SymTable(self.name, self.color, self.kind)
        new_st._symbols = dict(self._symbols)
        new_st.implicit_imports = set(self.implicit_imports)
        return new_st

    def add(self, sym: Symbol) -> None:
        # NOTE: we use slot_name as the key (compare and contrast with Scope.add)
        assert sym.slot_name not in self._symbols
        self._symbols[sym.slot_name] = sym

    def has_definition(self, name: str) -> bool:
        # KILL ME
        return name in self._symbols and self._symbols[name].is_local

    def lookup(self, name: str) -> Symbol:
        return self._symbols[name]

    def lookup_maybe(self, name: str) -> Optional[Symbol]:
        return self._symbols.get(name)

    def lookup_definition_maybe(self, name: str) -> Optional[Symbol]:
        """
        KILL ME: Like lookup_maybe, but find the symbol ONLY if it's a
        definition (i.e., if it's a local name).
        """
        sym = self._symbols.get(name)
        if sym and sym.is_local:
            return sym
        return None


def pp_symbols(header: str, symbols: dict[str, Symbol], indent: str) -> None:
    """
    Pretty-print a dict of symbols. Shared by Scope.pp and SymTable.pp.
    """
    color = ColorFormatter(use_colors=True)
    print(f"{indent}{header}")
    # sort symbols by:
    #   1. level
    #   2. color (const, then var)
    #   3. name (@special names last)
    sorted_symbols = sorted(
        symbols.values(),
        key=lambda sym: (sym.level, sym.varkind, sym.src_name.replace("@", "~")),
    )
    for sym in sorted_symbols:
        sym_color = "blue" if sym.varkind == "const" else "red"
        sym_name = color.set(sym_color, f"{sym.src_name:10s}")
        if sym.storage == "NameError":
            # special formatting
            print(f"{indent}    [ ] NameError  {sym_name}")
            continue

        impref = ""
        if sym.impref:
            impref = f" => {sym.impref}"
        storage = ""
        if sym.storage == "cell":
            storage = "[cell]"
        print(
            f"{indent}    [{sym.level}] {sym.varkind:5s} {sym_name} {storage} {impref}"
        )
