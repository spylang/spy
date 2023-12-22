from typing import Any, Optional
from spy import ast
from spy.vm.vm import SPyVM

def redshift(vm: SPyVM, mod: ast.Module) -> ast.Module:
    """
    Perform a redshift on the whole module
    """
    newdecls = []
    for decl in mod.decls:
        if isinstance(decl, ast.GlobalFuncDef):
            funcdef = decl.funcdef
            funcdef = FuncDefDoppler(funcdef).redshift()
            decl = decl.replace(funcdef=funcdef)
        newdecls.append(decl)
    return mod.replace(decls=newdecls)


class FuncDefDoppler:
    """
    Perform a redshift on a FuncDef
    """

    def __init__(self, funcdef: ast.FuncDef) -> None:
        self.funcdef = funcdef

    def redshift(self) -> ast.FuncDef:
        return self.funcdef # XXX
