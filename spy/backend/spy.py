from spy import ast
from spy.util import magic_dispatch
from spy.textbuilder import TextBuilder

class SPyBackend:
    """
    SPy backend: convert an AST back to SPy code.

    Mostly used for testing.
    """
    mod: ast.Module

    def __init__(self, mod: ast.Module) -> None:
        self.mod = mod
        self.out = TextBuilder(use_colors=False)

    def build(self):
        self.emit(self.mod)
        return self.out.build()

    def emit(self, node: ast.Node) -> None:
        magic_dispatch(self, 'emit', node)

    def emit_Module(self, mod: ast.Module) -> None:
        for decl in mod.decls:
            self.emit(decl)

    # declarations

    def emit_GlobalFuncDef(self, decl: ast.GlobalFuncDef) -> None:
        self.emit(decl.funcdef)

    # statements

    def emit_FuncDef(self, funcdef: ast.FuncDef) -> None:
        self.out.write(f'def {funcdef.name}(')
        # argument list
        for i, arg in enumerate(funcdef.args):
            is_last = (i == len(funcdef.args) - 1)
            self.out.write(f'{arg.name}: ')
            self.emit(arg.type)
            if not is_last:
                self.out.write(', ')
        # end argument list
        self.out.write(') -> ')
        self.emit(funcdef.return_type)
        self.out.writeline(':')
        with self.out.indent():
            for stmt in funcdef.body:
                self.emit(stmt)

    def emit_Pass(self, stmt: ast.Pass) -> None:
        self.out.writeline('pass')

    def emit_Return(self, ret: ast.Return) -> None:
        self.out.write('return ')
        self.emit(ret.value)

    # expressions

    def emit_Constant(self, const: ast.Constant) -> None:
        self.out.write(repr(const.value))

    def emit_Name(self, name: ast.Name) -> None:
        self.out.write(name.id)
