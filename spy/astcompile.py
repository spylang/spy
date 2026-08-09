"""
astcompile pass

The main job of this pass is to resolve names and symbols using the symtable collected
by ScopeAnalyzer.  In particular rewrites generic ast.Name into more specific
ast.NameLocalDirect, ast.NameOuterDirect, etc.

Moreover, do other easy desugaring like converting `for` loops into `while` loops, etc.
"""

import spy.ast as ast
from spy.analyze.symtable import SymTable
from spy.ast import LoweringStage
from spy.util import magic_dispatch


def astcompile(parsed_mod: ast.Module) -> ast.Module:
    assert parsed_mod.stage == "parsed"
    compiled_mod = ASTCompiler(parsed_mod).compile_mod()
    assert compiled_mod.stage == "astcompiled"
    compiled_mod.assert_valid_at("astcompiled")
    return compiled_mod


class ASTCompiler:
    def __init__(self, mod: ast.Module) -> None:
        self.mod = mod
        self.symtable_stack: list[SymTable] = []

    def push_symtable(self, symtable: SymTable) -> None:
        self.symtable_stack.append(symtable)

    def pop_symtable(self) -> SymTable:
        return self.symtable_stack.pop()

    @property
    def symtable(self) -> SymTable:
        return self.symtable_stack[-1]

    def compile_mod(self) -> ast.Module:
        self.push_symtable(self.mod.symtable)
        new_decls = [self.compile_decl(decl) for decl in self.mod.decls]
        self.pop_symtable()
        return self.mod.replace(
            stage="astcompiled",
            decls=new_decls,
        )

    def compile_decl(self, decl: ast.Decl) -> ast.Decl:
        return magic_dispatch(self, "compile_decl", decl)

    def compile_stmt(self, stmt: ast.Stmt) -> ast.Stmt:
        return magic_dispatch(self, "compile_stmt", stmt)

    def compile_expr(self, expr: ast.Expr) -> ast.Expr:
        return magic_dispatch(self, "compile_expr", expr)

    def compile_decl_NotImplemented(self, decl: ast.Decl) -> ast.Decl:
        return decl

    def compile_stmt_NotImplemented(self, stmt: ast.Stmt) -> ast.Stmt:
        return stmt

    def compile_expr_NotImplemented(self, expr: ast.Expr) -> ast.Expr:
        return expr

    # ===== Decl handlers =====

    def compile_decl_GlobalFuncDef(self, decl: ast.GlobalFuncDef) -> ast.Decl:
        new_funcdef = self.compile_funcdef(decl.funcdef)
        return decl.replace(funcdef=new_funcdef)

    ## def compile_decl_GlobalGenericFuncDef(
    ##     self, decl: ast.GlobalGenericFuncDef
    ## ) -> ast.Decl:
    ##     return decl

    ## def compile_decl_GlobalVarDef(self, decl: ast.GlobalVarDef) -> ast.Decl:
    ##     return decl

    ## def compile_decl_GlobalClassDef(self, decl: ast.GlobalClassDef) -> ast.Decl:
    ##     return decl

    ## def compile_decl_GlobalGenericClassDef(
    ##     self, decl: ast.GlobalGenericClassDef
    ## ) -> ast.Decl:
    ##     return decl

    ## def compile_decl_Import(self, decl: ast.Import) -> ast.Decl:
    ##     return decl

    # ===== FuncDef =====

    def compile_funcdef(self, funcdef: ast.FuncDef) -> ast.FuncDef:
        # TODO: decorators are evaluated in the outer scope
        ## for decorator in funcdef.decorators:
        ##     pass
        #
        # TODO: the TYPES of the arguments and defaults are evaluated in the outer scope
        new_return_type = self.compile_expr(funcdef.return_type)
        ## for arg in funcdef.args:
        ##     pass
        ## for default in funcdef.defaults:
        ##     pass

        # the statements of the function are evaluated in the inner scope
        self.push_symtable(funcdef.symtable)
        new_body = [self.compile_stmt(stmt) for stmt in funcdef.body]
        self.pop_symtable()
        return funcdef.replace(
            stage="astcompiled",
            return_type=new_return_type,
            body=new_body,
        )

    # ===== Stmt handlers =====

    def compile_stmt_Return(self, ret: ast.Return) -> ast.Stmt:
        return ret.replace(value=self.compile_expr(ret.value))

    def compile_stmt_Pass(self, stmt: ast.Pass) -> ast.Stmt:
        return stmt

    # ===== Expr handlers =====

    def compile_expr_Literal(self, expr: ast.Literal) -> ast.Expr:
        return expr

    def compile_expr_Name(self, name: ast.Name) -> ast.Expr:
        varname = name.id
        sym = self.symtable.lookup_maybe(varname)
        assert sym is not None

        # XXX: what about SPdb?
        ## if not self.is_interactive:
        ##     assert sym is not None

        ## if sym is None:
        ##     # sym can be None ONLY in interactive frames (in which case we do a dynamic
        ##     # lookup), else it means that there is a bug in symtable.
        ##     assert self.is_interactive, "sym not found"
        ##     # create a fake symbol to be used below
        ##     sym = Symbol(
        ##         varname,
        ##         "var",
        ##         "auto",
        ##         "NameError",
        ##         loc=name.loc,
        ##         type_loc=name.loc,
        ##         level=-1,
        ##     )

        if sym.impref is not None:
            return ast.NameImportRef(name.loc, sym)
        ## elif sym.storage == "direct" and sym.is_local:
        ##     assert False, "TODO"
        ##     # return ast.NameLocalDirect(name.loc, sym)
        ## elif sym.storage == "direct":
        ##     return ast.NameOuterDirect(name.loc, sym)
        ## elif sym.storage == "cell" and sym.is_local:
        ##     return ast.NameLocalCell(name.loc, sym)
        ## elif sym.storage == "cell":
        ##     outervars = self.closure[-sym.level]
        ##     w_cell = outervars[sym.name].w_val
        ##     assert isinstance(w_cell, W_Cell)
        ##     return ast.NameOuterCell(name.loc, sym, w_cell.fqn)
        elif sym.storage == "NameError":
            return ast.NameError(name.loc, name.id)
        else:
            return name  # TODO: handle remaining cases
