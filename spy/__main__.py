from typing import Annotated, Any, no_type_check
from pathlib import Path
import typer
import py.path
from spy.magic_py_parse import magic_py_parse
from spy.errors import SPyError
from spy.parser import Parser
from spy.backend.spy import SPyBackend
from spy.compiler import Compiler, ToolchainType
from spy.cbuild import get_toolchain
from spy.vm.b import B
from spy.vm.vm import SPyVM
from spy.vm.function import W_ASTFunc, W_Func, W_FuncType

app = typer.Typer(pretty_exceptions_enable=False)

def opt(T: type, help: str, names: tuple[str, ...]=()) -> Any:
    return Annotated[T, typer.Option(*names, help=help)]

def boolopt(help: str, names: tuple[str, ...]=()) -> Any:
    return opt(bool, help, names)

def do_pyparse(filename: str) -> None:
    import ast as py_ast
    with open(filename) as f:
        src = f.read()
    mod = magic_py_parse(src)
    mod.pp()

def dump_spy_mod(vm: SPyVM, modname: str, pretty: bool) -> None:
    fqn_format = 'short' if pretty else 'full'
    b = SPyBackend(vm, fqn_format=fqn_format)
    print(b.dump_mod(modname))

@no_type_check
@app.command()
def main(filename: Path,
         run: boolopt("run the file") = False,
         pyparse: boolopt("dump the Python AST exit") = False,
         parse: boolopt("dump the SPy AST and exit") = False,
         redshift: boolopt("perform redshift and exit") = False,
         cwrite: boolopt("create the .c file and exit") = False,
         g: boolopt("generate debug symbols", names=['-g']) = False,
         O: opt(int, "optimization level", names=['-O']) = 0,
         release_mode: boolopt(
             "enable release mode", names=['-r', '--release']
         ) = False,
         toolchain: opt(
             ToolchainType,
             "which compiler to use",
             names=['--toolchain', '-t']
         ) = "zig",
         pretty: boolopt("prettify redshifted modules") = True,
         ) -> None:
    try:
        do_main(filename, run, pyparse, parse, redshift, cwrite, g, O,
                release_mode, toolchain, pretty)
    except SPyError as e:
        print(e.format(use_colors=True))
        #import pdb;pdb.xpm()

def do_main(filename: Path, run: bool, pyparse: bool, parse: bool,
            redshift: bool,
            cwrite: bool,
            debug_symbols: bool,
            opt_level: int,
            release_mode: bool,
            toolchain: ToolchainType,
            pretty: bool) -> None:
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
        w_main = w_mod.getattr_maybe('main')
        if w_main is None:
            print('Cannot find function main()')
            return
        vm.typecheck(w_main, w_main_functype)
        assert isinstance(w_main, W_Func)
        w_res = vm.call(w_main, [])
        assert w_res is B.w_None
        return

    vm.redshift()
    if redshift:
        dump_spy_mod(vm, modname, pretty)
        return

    compiler = Compiler(vm, modname, py.path.local(builddir),
                        dump_c=False)
    if cwrite:
        t = get_toolchain(toolchain)
        compiler.cwrite(t.TARGET)
    else:
        compiler.cbuild(
            opt_level=opt_level,
            debug_symbols=debug_symbols,
            toolchain_type=toolchain,
            release_mode=release_mode,
        )

if __name__ == '__main__':
    app()
