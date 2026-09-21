# ================== IMPORTANT: .spyc versioning =================
# Update importing.SPYC_VERSION in case of any significant change
# ================================================================

import pprint
import re
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
# "decl-global" (and later "decl-nonlocal") marks an analysis-only marker Symbol
# placed in a Scope by a `global x` declaration.  It never appears in a SymTable
# and is never bound to a node at runtime (see scope.collect_Global).
#
# "decl-cannot-lift" marks an explicit decl below a lift target, so a later
# implicit declaration of the same name in the target is rejected
# ([py.scope-lifting-mixing-error]).
VarStorage = Literal["direct", "cell", "decl-global", "decl-cannot-lift"]
VarKind = Literal["var", "const"]

# how the name entered the scope
DeclOrigin = Literal[
    "explicit",  # var/const, params, funcdef, etc.
    "implicit",  # bare assignment
]
VarKindOrigin = Literal[
    "auto",          # "x = 0" inside a function
    "global-const",  # "x = 0" at module level
    "explicit",      # "var x = 0" or "const x = 0"
    "funcdef",       # function defs are always "const"
    "classdef",      # class defs are always "const"
    "class-field",   # class field declarations are always "var"
    "red-param",     # parameters of red functions are "var"
    "blue-param",    # parameters of blue functions are "const"
    "loop-target",   # the "i" in "for i in ..." ([scope.loop-target])
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
    decl_origin: DeclOrigin = "explicit"
    slot_name: str
    loc: Loc  # where the symbol is defined, in the source code
    type_loc: Loc  # loc of the TYPE of the symbols

    # frame_depth indicates in which scope the symbol resides:
    #   0: this Symbol is defined in the scope corresponding to
    #      the current SymTable (i.e., it's a "local variable")
    #   1: this is the most immediate outer scope
    #   2: the outer-outer, etc.
    #
    # E.g., for a module-level funcdef, we have three levels:
    #   * 0: local variables inside the funcdef
    #   * 1: module-level scope
    #   * 2: builtins
    frame_depth: int
    impref: Optional[ImportRef] = None

    def replace(self, **kwargs: Any) -> "Symbol":
        return replace(self, **kwargs)

    @property
    def is_local(self) -> bool:
        return self.frame_depth == 0

    def pp(self) -> None:
        pprint.pprint(self)


@dataclass(frozen=True)
class LookupResult:
    """
    The result of Scope.lookup.
    """

    frame_depth: int  # number of symtables crossed; -1 if not found.
    scope: Optional["Scope"]
    sym: Optional[Symbol]
    has_global_decl: bool  # was there a `global x` declaration in a scope?

    @property
    def found(self) -> bool:
        return self.frame_depth != -1


class Scope:
    """
    A lexical scope, as seen by the ScopeAnalyzer (scope.py) during the bind
    and resolve passes.  Scopes are nested and correspond to a lexical region
    (function, module, block).

    A Scope is an ANALYSIS-ONLY concept: it is created by ScopeAnalyzer and
    discarded afterwards.
    """

    name: str
    color: Color
    kind: ScopeKind
    symtable: "SymTable"
    symbols: dict[str, Symbol]  # names declared in this scope

    # lexical tree links, wired at construction (see __init__): a scope appends
    # itself to its parent's children.
    parent: Optional["Scope"]
    children: list["Scope"]

    def __init__(
        self,
        name: str,
        color: Color,
        kind: ScopeKind,
        *,
        symtable: "SymTable",
        parent: Optional["Scope"],
    ) -> None:
        self.name = name
        self.color = color
        self.kind = kind
        self.symbols = {}
        self.symtable = symtable
        self.children = []
        self.parent = parent
        if parent is not None:
            parent.children.append(self)

    @property
    def short_name(self) -> str:
        """
        The last component of the (possibly '::'-separated) scope name.
        """
        return self.name.rsplit("::", 1)[-1]

    @property
    def is_lift_target(self) -> bool:
        """
        [py.scope-lifting]: an implicit declaration lifts up to the nearest lift
        target. A lift target is a frame owner (function/module/class) or a loop
        body. Every other block (if/else, and later try/with) is transparent.
        """
        if self.kind != "block":
            return True  # a frame owner
        return self.short_name in ("for.body", "while.body")

    @classmethod
    def from_builtins(cls) -> "Scope":
        from spy.vm.b import BUILTINS
        from spy.vm.function import W_BuiltinFunc

        # the builtins symtable is empty because it should never be reached at
        # runtime: all builtins lookups are resolved at the scope level.
        symtable = SymTable("builtins", "blue", "module")
        scope = cls("builtins", "blue", "module", symtable=symtable, parent=None)
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
                frame_depth=0,
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

    def pp(self, indent: str = "") -> None:
        pp_symbols(repr(self), self.symbols, indent)

    def add(self, sym: Symbol) -> None:
        # NOTE: we use src_name as the key (compare and contrast with SymTable.add)
        assert sym.src_name not in self.symbols
        self.symbols[sym.src_name] = sym

    def remove(self, name: str) -> None:
        del self.symbols[name]

    def lookup(self, name: str) -> LookupResult:
        """
        Resolve `name` using the full scoping rules: start from this scope and walk
        outward along the `parent` chain.
        """
        # frame_depth counts how many runtime frame boundaries we cross. It is used
        # to index inside frame.closure; frame_depth==0 means "local frame".
        frame_depth = 0
        has_global_decl = False
        scope: Optional[Scope] = self
        while scope is not None:
            if scope.kind == "class" and frame_depth > 0:
                # [name.class-skip]: jump over class scopes
                scope = scope.parent
                continue
            sym = scope.symbols.get(name)
            if sym is not None:
                if sym.storage == "decl-global":
                    # `global name`: record it and keep walking
                    has_global_decl = True
                elif sym.storage == "decl-cannot-lift":
                    pass  # just a marker, keep walking
                else:
                    return LookupResult(frame_depth, scope, sym, has_global_decl)
            if scope.kind in ("function", "module", "class"):
                # we are leaving a runtime frame
                frame_depth += 1
            scope = scope.parent
        return LookupResult(-1, None, None, has_global_decl)


class SymTable:
    """
    A flat, per-frame runtime namespace.  It is attached to a FuncDef/ClassDef/
    Module and used at runtime by the frames to index their locals. It contains the
    definition of all the "local variables" of a given frame.

    SymTable also record the color of the frame which it corresponds to:

      - frames associated to red functions are RED

      - frames associated to blue functions are BLUE

      - frames associated to modules, classdefs, etc. are also BLUE
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
        builtins_scope = Scope.from_builtins()
        symtable = cls(builtins_scope.name, builtins_scope.color, builtins_scope.kind)
        symtable._symbols = dict(builtins_scope.symbols)
        return symtable

    def __repr__(self) -> str:
        return f"<SymTable '{self.name}' ({self.color}, {self.kind})>"

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

    def make_temp_symbol(self, base: str, loc: Loc) -> Symbol:
        """
        Allocate and register a hidden compiler temporary (e.g. `_$iter`) in this
        frame, returning its Symbol.  It's a "var/auto/direct".
        """
        slot_name = self.get_fresh_slot(base)
        sym = Symbol(
            base,
            "var",
            "auto",
            "direct",
            slot_name=slot_name,
            loc=loc,
            type_loc=loc,
            frame_depth=0,
        )
        self.add(sym)
        return sym

    def get_fresh_slot(self, src_name: str) -> str:
        """
        Get a fresh, unique slot name for the given src_name, in the form `x$0`,
        `x$1`, etc.

        Names are mangled only inside function frames.  Module- and class-level
        names must stay accessible by their source name (they are exposed as
        module/class attributes and referenced by FQN), so they are not mangled.

        `@`-names (e.g. `@return`, `@if`) are special: they are declared and
        looked up literally at runtime, so they are never mangled.

        If `src_name` is already uniquely indexed with a `$NUM` suffix (e.g. `_$iter$0`)
        we avoid double-suffixing (`_$iter$0$0`) and compute a fresh `<base>$n` instead.
        """
        if self.kind != "function" or src_name.startswith("@"):
            return src_name
        base = src_name
        m = re.fullmatch(r"(.*)\$\d+", src_name)
        if m:
            base = m.group(1)
        n = 0
        while (slot_name := f"{base}${n}") in self._symbols:
            n += 1
        return slot_name

    def lookup(self, name: str) -> Symbol:
        return self._symbols[name]

    def lookup_maybe(self, name: str) -> Optional[Symbol]:
        return self._symbols.get(name)


def pp_symbols(header: str, symbols: dict[str, Symbol], indent: str) -> None:
    """
    Pretty-print a dict of symbols. Shared by Scope.pp and SymTable.pp.
    """
    color = ColorFormatter(use_colors=True)
    print(f"{indent}{header}")
    # sort symbols by:
    #   1. frame_depth
    #   2. color (const, then var)
    #   3. name (@special names last)
    sorted_symbols = sorted(
        symbols.values(),
        key=lambda sym: (sym.frame_depth, sym.varkind, sym.src_name.replace("@", "~")),
    )
    for sym in sorted_symbols:
        sym_color = "blue" if sym.varkind == "const" else "red"
        sym_name = color.set(sym_color, f"{sym.src_name:10s}")
        impref = ""
        if sym.impref:
            impref = f" => {sym.impref}"
        storage = ""
        if sym.storage == "cell":
            storage = "[cell]"
        print(
            f"{indent}    [{sym.frame_depth}] {sym.varkind:5s} {sym_name} {storage} {impref}"
        )
