import sys
from typing import Annotated, Any, no_type_check, Optional
import asyncio
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
from spy.doppler import ErrorMode
from spy.compiler import Compiler, ToolchainType
from spy.cbuild import get_toolchain, BUILD_TYPE
from spy.textbuilder import Color
from spy.irgen.scope import ScopeAnalyzer
from spy.vm.b import B
from spy.vm.vm import SPyVM
from spy.vm.function import W_ASTFunc, W_Func, W_FuncType
from spy.util import highlight_C_maybe
import traceback
import functools

app = typer.Typer(pretty_exceptions_enable=False)

@dataclass
class Arguments:
    filename: Path

    execute: Annotated[
        bool,
        Option(
            "-x", "--execute",
            help="Execute the file (default)"
        )
    ] = False

    pyparse: Annotated[
        bool,
        Option(
            "-P", "--pyparse",
            help="Dump the Python AST"
        )
    ] = False

    parse: Annotated[
        bool,
        Option(
            "-p", "--parse",
            help="Dump the SPy AST"
        )
    ] = False

    symtable: Annotated[
        bool,
        Option(
            "-S", "--symtable",
            help="Dump the symtables"
        )
    ] = False

    redshift: Annotated[
        bool,
        Option(
            "-r", "--redshift",
            help="Perform redshift and dump the result"
        )
    ] = False

    cwrite: Annotated[
        bool,
        Option(
            "-C", "--cwrite",
            help="Generate the C code"
        )
    ] = False

    cdump: Annotated[
        bool,
        Option(
            "--cdump",
            help="Dump the generated C code to stdout"
        )
    ] = False

    compile: Annotated[
        bool,
        Option(
            "-c", "--compile",
            help="Compile the generated C code"
        )
    ] = False

    build_dir: Annotated[
        Optional[Path],
        Option(
            "-b", "--build-dir",
            help="Directory to store generated files (defaults to build/ next to the .spy file)"
        )
    ] = None

    opt_level: Annotated[
        int,
        Option(
            '-O', metavar='LEVEL',
            help="Optimization level",
        )
    ] = 0

    debug_symbols: Annotated[
        bool,
        Option(
            '-g',
            help="Generate debug symbols"
        )
    ] = False

    release_mode: Annotated[
        bool,
        Option(
            '--release',
            help="enable release mode"
        )
    ] = False

    toolchain: Annotated[
        ToolchainType,
        Option(
            "-t", "--toolchain",
            help="which compiler to use"
        )
    ] = ToolchainType.zig

    error_mode: Annotated[
        ErrorMode,
        Option(
            "-E", "--error-mode",
            help="Handling strategy for static errors",
            click_type=click.Choice(ErrorMode.__args__),
        )
    ] = 'eager'

    full_fqn: Annotated[
        bool,
        Option(
            "--full-fqn",
            help="Show full FQNs in redshifted modules"
        )
    ] = False

    timeit: Annotated[
        bool,
        Option(
            "--timeit",
            help="Print execution time"
        )
    ] = False

    pdb: Annotated[
        bool,
        Option(
            "--pdb",
            help="Enter interp-level debugger in case of error"
        )
    ] = False

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
        elif actions == {"redshift", "execute"} or actions == {"redshift", "parse"}:
            pass # these are valid
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

def dump_spy_mod(vm: SPyVM, modname: str, full_fqn: bool) -> None:
    fqn_format: FQN_FORMAT = 'full' if full_fqn else 'short'
    b = SPyBackend(vm, fqn_format=fqn_format)
    print(b.dump_mod(modname))

def dump_spy_mod_ast(vm: SPyVM, modname: str) -> None:
    w_mod = vm.modules_w[modname]
    for fqn, w_obj in w_mod.items_w():
        if (isinstance(w_obj, W_ASTFunc) and
            w_obj.color == 'red' and
            w_obj.fqn == fqn):
            print(f'`{fqn}` = ', end='')
            w_obj.funcdef.pp()
            print()

def pyproject_entry_point() -> Any:
    """
    This is called by the script generated by pyproject.toml
    """
    if sys.platform == 'emscripten':
        print("The 'spy' command does not work in a pyodide venv running under node. Please use python -m spy")
        sys.exit(1)
    return app()

@app.command()
@dataclass_typer
def main(args: Arguments) -> None:
    # this is the main Typer entry point
    if sys.platform == 'emscripten':
        asyncio.create_task(pyodide_main(args))
    else:
        asyncio.run(real_main(args))


async def pyodide_main(args: Arguments) -> None:
    """
    For some reasons, it seems that pyodide doesn't print exceptions
    uncaught exceptions which escapes an asyncio task. This is a small wrapper
    to ensure that we display a proper traceback in that case
    """
    try:
        await real_main(args)
    except BaseException:
       traceback.print_exc()

async def real_main(args: Arguments) -> None:
    """
    A wrapper around inner_main, to catch/display SPy errors and to
    implement --pdb
    """
    try:
        return await inner_main(args)
    except SPyError as e:
        print(e.format(use_colors=True))
        if args.pdb:
            info = sys.exc_info()
            stdlib_pdb.post_mortem(info[2])
        sys.exit(1)
    except Exception as e:
        if not args.pdb:
            raise
        traceback.print_exc()
        info = sys.exc_info()
        stdlib_pdb.post_mortem(info[2])
        sys.exit(1)


def emit_warning(err: SPyError) -> None:
    print(Color.set('yellow', '[warning] '), end='')
    print(err.format())

async def inner_main(args: Arguments) -> None:
    """
    The actual code for the spy executable
    """
    if args.pyparse:
        do_pyparse(str(args.filename))
        return

    modname = args.filename.stem
    srcdir = args.filename.parent
    vm = await SPyVM.async_new()

    vm.path.append(str(srcdir))
    if args.error_mode == 'warn':
        args.error_mode = 'lazy'
        vm.emit_warning = emit_warning

    # Determine build directory
    if args.build_dir is not None:
        builddir = args.build_dir
        builddir.mkdir(exist_ok=True, parents=True)
    elif args.cwrite or args.compile:
        # Create a build directory next to the .spy file
        builddir = srcdir / "build"
        builddir.mkdir(exist_ok=True, parents=True)
        print(f"Using build directory: {builddir}")
    else:
        # For non-build operations, use the source directory
        builddir = srcdir

    if (args.parse and not args.redshift) or args.symtable:
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

    vm.redshift(error_mode=args.error_mode)
    if args.redshift:
        if args.parse:
            dump_spy_mod_ast(vm, modname)
        else:
            dump_spy_mod(vm, modname, args.full_fqn)
        return

    compiler = Compiler(vm, modname, py.path.local(str(builddir)),
                        dump_c=False)
    if args.cwrite:
        build_type: BUILD_TYPE = "release" if args.release_mode else "debug"
        t = get_toolchain(args.toolchain, build_type=build_type)
        file_c = compiler.cwrite(t.TARGET)
        print(f"Generated {file_c}")
        if args.cdump:
            print(highlight_C_maybe(file_c.read()))

    else:
        executable = compiler.cbuild(
            opt_level=args.opt_level,
            debug_symbols=args.debug_symbols,
            toolchain_type=args.toolchain,
            release_mode=args.release_mode,
        )
        print(f"Generated {executable}")
