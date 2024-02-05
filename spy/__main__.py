from typing import Annotated, Any, no_type_check
from pathlib import Path
import typer
import py.path
from spy.magic_py_parse import magic_py_parse
from spy.errors import SPyError
from spy.parser import Parser
from spy.backend.spy import SPyBackend
from spy.compiler import Compiler
from spy.vm.b import B
from spy.vm.vm import SPyVM
from spy.vm.function import W_ASTFunc, W_Func, W_FuncType

app = typer.Typer(pretty_exceptions_enable=False)

def boolopt(help: str, names: tuple[str, ...]=()) -> Any:
    return Annotated[bool, typer.Option(*names, help=help)]

def do_pyparse(filename: str) -> None:
    import ast as py_ast
    with open(filename) as f:
        src = f.read()
    mod = magic_py_parse(src)
    mod.pp()

def dump_spy_mod(vm: SPyVM, modname: str) -> None:
    b = SPyBackend(vm, fqn_format='short')
    w_mod = vm.modules_w[modname]
    for fqn, w_obj in w_mod.items_w():
        if isinstance(w_obj, W_ASTFunc):
            print(b.dump_w_func(w_obj))



@no_type_check
@app.command()
def main(filename: Path,
         run: boolopt("run the file") = False,
         pyparse: boolopt("dump the Python AST exit") = False,
         parse: boolopt("dump the SPy AST and exit") = False,
         redshift: boolopt("perform redshift and exit") = False,
         cwrite: boolopt("create the .c file and exit") = False,
         g: boolopt("generate debug symbols", names=['-g']) = False,
         ) -> None:
    try:
        do_main(filename, run, pyparse, parse, redshift, cwrite, g)
    except SPyError as e:
        print(e.format(use_colors=True))

def do_main(filename: Path, run: bool, pyparse: bool, parse: bool,
            redshift: bool,
            cwrite: bool, debug_symbols: bool) -> None:
    if pyparse:
        do_pyparse(str(filename))
        return

    if parse:
        parser = Parser.from_filename(str(filename))
        mod = parser.parse()
        mod.pp()
        return

    modname = filename.stem
    builddir = filename.parent
    vm = SPyVM()
    vm.path.append(str(builddir))
    w_mod = vm.import_(modname)

    if run:
        w_main_functype = W_FuncType.parse('def() -> void')
        w_main = w_mod.getattr('main')
        vm.typecheck(w_main, w_main_functype)
        assert isinstance(w_main, W_Func)
        w_res = vm.call_function(w_main, [])
        if w_res is not B.w_None:
            B.w_print.pyfunc(vm, w_res)
        return

    vm.redshift()
    if redshift:
        dump_spy_mod(vm, modname)
        return

    compiler = Compiler(vm, modname, py.path.local(builddir))
    if cwrite:
        compiler.cwrite()
    else:
        compiler.cbuild(debug_symbols=debug_symbols)

if __name__ == '__main__':
    app()
