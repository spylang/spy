from typing import TYPE_CHECKING

from spy import ast
from spy.analyze.scope import ScopeAnalyzer
from spy.analyze.symtable import Color, SymTable
from spy.errors import SPyError
from spy.fqn import FQN
from spy.vm.astframe import AbstractFrame
from spy.vm.cell import W_Cell
from spy.vm.function import W_ASTFunc
from spy.vm.module import W_Module
from spy.vm.object import W_Object

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


class ModFrame(AbstractFrame):
    """
    A frame to execute the body of a module
    """

    vm: "SPyVM"
    modname: str
    mod: ast.Module
    scopes: ScopeAnalyzer

    def __init__(
        self,
        vm: "SPyVM",
        ns: FQN,
        mod: ast.Module,
    ) -> None:
        assert mod.symtable is not None
        assert mod.symtable.kind == "module"
        super().__init__(vm, ns, mod.loc, mod.symtable, closure=())
        self.mod = mod
        self.w_mod = W_Module(ns.modname, mod.filename)
        self.vm.register_module(self.w_mod)
        self.declare_reserved_bool_locals()

    def __repr__(self) -> str:
        cls = self.__class__.__name__
        return f"<{cls} for `{self.ns}`>"

    def store_local(self, name: str, w_value: W_Object) -> None:
        # For modules, locals also go directly in the module dict
        super().store_local(name, w_value)
        self.w_mod._dict_w[name] = w_value

    def run(self) -> W_Module:
        # forward declaration of types
        for decl in self.mod.decls:
            if isinstance(decl, ast.GlobalClassDef):
                self.fwdecl_ClassDef(decl.classdef)

        for decl in self.mod.decls:
            if isinstance(decl, ast.Import):
                self.exec_Import(decl)
            elif isinstance(decl, ast.GlobalFuncDef):
                self.exec_stmt(decl.funcdef)
            elif isinstance(decl, ast.GlobalClassDef):
                self.exec_stmt(decl.classdef)
            elif isinstance(decl, ast.GlobalVarDef):
                self.exec_GlobalVarDef(decl)
            else:
                assert False
        #
        # call the __INIT__, if present
        w_init = self.w_mod.getattr_maybe("__INIT__")
        if w_init is not None:
            assert isinstance(w_init, W_ASTFunc)
            if w_init.color != "blue":
                err = SPyError(
                    "W_TypeError",
                    "the __INIT__ function must be @blue",
                )
                err.add("error", "function defined here", w_init.def_loc)
                raise err
            self.vm.fast_call(w_init, [self.w_mod])
        #
        return self.w_mod

    def exec_GlobalVarDef(self, decl: ast.GlobalVarDef) -> None:
        vardef = decl.vardef
        varname = vardef.name.value
        fqn = self.ns.join(varname)
        sym = self.symtable.lookup(varname)
        assert sym.level == 0, "module assign to name declared outside?"

        # evaluate the right side of the vardef
        assert vardef.value is not None
        wam = self.eval_expr(vardef.value)

        # declare the variable
        color: Color = "blue" if vardef.kind == "const" else "red"
        is_auto = isinstance(vardef.type, ast.Auto)
        if is_auto:
            w_T = wam.w_static_T
        else:
            w_T = self.eval_expr_type(vardef.type)
        self.declare_local(varname, color, w_T, vardef.loc)

        # do the assignment
        if sym.storage == "direct":
            self.store_local(sym.name, wam.w_val)

        elif sym.storage == "cell":
            w_cell = W_Cell(fqn, wam.w_val)
            self.vm.add_global(fqn, w_cell)
            self.store_local(sym.name, w_cell)

        else:
            assert False

    # NOTE: ast.Import is not (yet?) a statement
    def exec_Import(self, imp: ast.Import) -> None:
        sym = self.symtable.lookup(imp.asname)
        assert sym.is_local
        assert sym.impref == imp.ref
        w_val = self.vm.lookup_ImportRef(imp.ref)
        if w_val is not None:
            # import successful, nothing to do.
            return

        # import failed, raise ImportError
        err = SPyError(
            "W_ImportError",
            f"cannot import `{imp.ref.spy_name()}`",
        )
        if imp.ref.modname not in self.vm.modules_w:
            # See if there is a matching .py file
            if self.vm.find_file_on_path(imp.ref.modname, allow_py_files=True):
                err.add(
                    "error",
                    f"file `{imp.ref.modname}.py` exists, but py files cannot be imported",
                    loc=imp.loc,
                )
            else:
                # module not found
                err.add(
                    "error", f"module `{imp.ref.modname}` does not exist", loc=imp.loc
                )
        else:
            # attribute not found
            err.add(
                "error",
                f"attribute `{imp.ref.attr}` does not exist "
                + f"in module `{imp.ref.modname}`",
                loc=imp.loc_asname,
            )
        raise err
