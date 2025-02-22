import sys
from typing import Annotated, Any, no_type_check, Optional
from pathlib import Path
import time
import traceback
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
from spy.cbuild import get_toolchain, BUILD_TYPE
from spy.irgen.scope import ScopeAnalyzer
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
    symtable: bool = Option(False,
        "-S", "--symtable",
        help="Dump the symtables"
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
        '--release',
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

    def __post_init__(self) -> None:
        self.validate_actions()
        if not self.filename.exists():
            raise typer.BadParameter(f"File {self.filename} does not exist")

    def validate_actions(self) -> None:
        # check that we specify at most one of the following options
        possible_actions = ["execute", "pyparse", "parse", "symtable",
                            "redshift", "cwrite", "compile"]
        actions = {a for a in possible_actions if getattr(self, a)}
        n = len(actions)
        if n == 0:
            self.execute = True
        elif n == 1:
            pass # this is valid
        elif actions == {"execute", "redshift"}:
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
    except Exception as e:
        if not args.pdb:
            raise

        traceback.print_exc()
        info = sys.exc_info()
        stdlib_pdb.post_mortem(info[2])


def do_main(args: Arguments) -> None:
    if args.pyparse:
        do_pyparse(str(args.filename))
        return

    modname = args.filename.stem
    builddir = args.filename.parent
    vm = SPyVM()
    vm.path.append(str(builddir))

    if args.parse or args.symtable:
        parser = Parser.from_filename(str(args.filename))
        mod = parser.parse()
        if args.parse:
            mod.pp()
        elif args.symtable:
            scopes = ScopeAnalyzer(vm, modname, mod)
            scopes.analyze()
            scopes.pp()
        return

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
        build_type: BUILD_TYPE = "release" if args.release_mode else "debug"
        t = get_toolchain(args.toolchain, build_type=build_type)
        compiler.cwrite(t.TARGET)
    else:
        compiler.cbuild(
            opt_level=args.opt_level,
            debug_symbols=args.debug_symbols,
            toolchain_type=args.toolchain,
            release_mode=args.release_mode,
        )
