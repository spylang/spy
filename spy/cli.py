import sys
from typing import Annotated, Any, Optional
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
from spy.analyze.importing import ImportAnalizyer
from spy.errors import SPyError
from spy.backend.spy import SPyBackend, FQN_FORMAT
from spy.doppler import ErrorMode
from spy.backend.c.cbackend import CBackend
from spy.build.config import BuildConfig, BuildTarget, OutputKind
from spy.textbuilder import Color
from spy.vm.b import B
from spy.vm.vm import SPyVM
from spy.vm.function import W_ASTFunc, W_Func, W_FuncType
import traceback

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

    colorize: Annotated[
        bool,
        Option(
            "-C", "--colorize",
            help="Output the redshifted AST with blue / red text colors."
        )
    ] = False

    imports: Annotated[
        bool,
        Option(
            "-I", "--imports",
            help="Dump the (recursive) list of imports"
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

    target: Annotated[
        BuildTarget,
        Option(
            "-t", "--target",
            help="Compilation target",
            click_type=click.Choice(BuildTarget.__args__),
        )
    ] = 'native'

    output_kind: Annotated[
        OutputKind,
        Option(
            "-k", "--output-kind",
            help="Output kind",
            click_type=click.Choice(OutputKind.__args__),
        )
    ] = 'exe'

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
        possible_actions = ["execute", "pyparse", "parse",
                            "imports", "symtable",
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
    with open(filename) as f:
        src = f.read()
    mod = magic_py_parse(src)
    mod.pp()

def dump_spy_mod(vm: SPyVM, modname: str, full_fqn: bool) -> None:
    fqn_format: FQN_FORMAT = 'full' if full_fqn else 'short'
    b = SPyBackend(vm, fqn_format=fqn_format)
    print(b.dump_mod(modname))

def dump_spy_mod_ast(vm: SPyVM, modname: str, colorize: bool=False) -> None:
    print(f"{colorize=}")
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

def get_build_dir(args: Arguments) -> py.path.local:
    if args.build_dir is not None:
        build_dir = args.build_dir
    else:
        # Create a build directory next to the .spy file
        srcdir = args.filename.parent
        build_dir = srcdir / "build"

    #print(f"Build dir:    {build_dir}")
    build_dir.mkdir(exist_ok=True, parents=True)
    return py.path.local(str(build_dir))


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

    importer = ImportAnalizyer(vm, modname)
    importer.parse_all()

    if args.parse and not args.redshift:
        mod = importer.getmod(modname)
        print(f"{mod=}")
        mod.pp(colorize=args.colorize)
        return

    if args.imports:
        importer.pp()
        return

    if args.symtable:
        scopes = importer.analyze_scopes(modname)
        scopes.pp()
        return

    importer.import_all()
    w_mod = vm.modules_w[modname]

    #vm.pp_globals()
    #vm.pp_modules()

    if args.execute:
        w_main_functype = W_FuncType.parse('def() -> None')
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
            dump_spy_mod_ast(vm, modname, colorize=args.colorize)
        else:
            dump_spy_mod(vm, modname, args.full_fqn)
        return

    config = BuildConfig(
        target = args.target,
        kind = args.output_kind,
        build_type = "release" if args.release_mode else "debug"
    )

    cwd = py.path.local('.')
    build_dir = get_build_dir(args)
    dump_c = args.cwrite and args.cdump
    backend = CBackend(
        vm,
        modname,
        config,
        build_dir,
        dump_c=dump_c
    )

    backend.cwrite()
    backend.write_build_script()
    assert backend.build_script is not None

    if args.cwrite:
        cfiles = ', '.join([f.relto(cwd) for f in backend.cfiles])
        build_script = backend.build_script.relto(cwd)
        print(f"C files:      {cfiles}")
        print(f"Build script: {build_script}")
        return

    outfile = backend.build()
    executable = outfile.relto(cwd)
    print(f"==> {executable}")
