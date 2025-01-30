import sys
from typing import Annotated, Any, no_type_check, Optional
from pathlib import Path
import time
from dataclasses import dataclass
import click
import typer
from typer import Option
import py.path
import pdb as stdlib_pdb # to distinguish from the "--pdb" option
from spy.vendored.dataclass_typer import dataclass_typer
from spy.magic_py_parse import magic_py_parse
from spy.errors import SPyError
from spy.parser import Parser
from spy.backend.spy import SPyBackend, FQN_FORMAT
from spy.compiler import Compiler, ToolchainType
from spy.cbuild import get_toolchain
from spy.vm.b import B
from spy.vm.vm import SPyVM
from spy.vm.function import W_ASTFunc, W_Func, W_FuncType

app = typer.Typer(pretty_exceptions_enable=False)


@dataclass
class Arguments:
    filename: Path

    execute: bool = Option(False,
        "-x", "--execute",
        help="Execute the file (default)"
    )
    pyparse: bool = Option(False,
        "-P", "--pyparse",
        help="Dump the Python AST"
    )
    parse: bool = Option(False,
        "-p", "--parse",
        help="Dump the SPy AST"
    )
    redshift: bool = Option(False,
        "-r", "--redshift",
        help="Perform redshift and dump the result"
    )
    cwrite: bool = Option(False,
        "-C", "--cwrite",
        help="Generate the C code"
    )
    compile: bool = Option(False,
        "-c", "--compile",
        help="Compile the generated C code"
    )
    opt_level: int = Option(0,
        '-O',
        metavar='LEVEL',
        help="Optimization level",
    )
    debug_symbols: bool = Option(False,
        '-g',
        help="Generate debug symbols"
    )
    release_mode: bool = Option(False,
        '-r', '--release',
        help="enable release mode"
    )
    toolchain: ToolchainType = Option("zig",
        "-t", "--toolchain",
        help="which compiler to use"
    )
    pretty: bool = Option(True,
        help="Prettify redshifted modules"
    )
    timeit: bool = Option(False,
        "--timeit",
        help="Print execution time"
    )
    pdb: bool = Option(False,
        "--pdb",
        help="Enter interp-level debugger in case of error"
    )

    def __post_init__(self):
        # check that we specify at most one of the following options
        possible_actions = ["execute", "pyparse", "parse", "redshift", "cwrite", "compile"]
        actions = {a for a in possible_actions if getattr(self, a)}
        n = len(actions)
        if n == 0:
            self.execute = True
        elif n == 1:
            pass # this is valid
        elif n == {"execute", "redshift"}:
            pass # this is valid
        else:
            msg = "Too many actions specified: "
            msg += " ".join(["--" + a for a in actions])
            raise typer.BadParameter(msg)





def do_pyparse(filename: str) -> None:
    import ast as py_ast
    with open(filename) as f:
        src = f.read()
    mod = magic_py_parse(src)
    mod.pp()

def dump_spy_mod(vm: SPyVM, modname: str, pretty: bool) -> None:
    fqn_format: FQN_FORMAT = 'short' if pretty else 'full'
    b = SPyBackend(vm, fqn_format=fqn_format)
    print(b.dump_mod(modname))

@no_type_check
@app.command()
@dataclass_typer
def main(args: Arguments) -> None:
    ""
    try:
        do_main(args)
    except SPyError as e:
        print(e.format(use_colors=True))
        if args.pdb:
            info = sys.exc_info()
            stdlib_pdb.post_mortem(info[2])


def do_main(args: Arguments) -> None:
    if args.pyparse:
        do_pyparse(str(args.filename))
        return

    if args.parse:
        parser = Parser.from_filename(str(args.filename))
        mod = parser.parse()
        mod.pp()
        return

    modname = args.filename.stem
    builddir = args.filename.parent
    vm = SPyVM()
    vm.path.append(str(builddir))
    w_mod = vm.import_(modname)

    if args.execute:
        w_main_functype = W_FuncType.parse('def() -> void')
        w_main = w_mod.getattr_maybe('main')
        if w_main is None:
            print('Cannot find function main()')
            return
        vm.typecheck(w_main, w_main_functype)
        assert isinstance(w_main, W_Func)
        a = time.time()
        w_res = vm.fast_call(w_main, [])
        b = time.time()
        if args.timeit:
            print(f'main(): {b - a:.3f} seconds', file=sys.stderr)
        assert w_res is B.w_None

        return

    vm.redshift()
    if args.redshift:
        dump_spy_mod(vm, modname, args.pretty)
        return

    compiler = Compiler(vm, modname, py.path.local(builddir),
                        dump_c=False)
    if args.cwrite:
        t = get_toolchain(args.toolchain)
        compiler.cwrite(t.TARGET)
    else:
        compiler.cbuild(
            opt_level=args.opt_level,
            debug_symbols=args.debug_symbols,
            toolchain_type=args.toolchain,
            release_mode=args.release_mode,
        )

if __name__ == '__main__':
    app()
