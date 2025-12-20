import asyncio
import os
import pdb as stdlib_pdb  # to distinguish from the "--pdb" option
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Optional

import click
import py.path
import typer
from typer import Argument, Option

from spy.analyze.importing import ImportAnalyzer
from spy.backend.c.cbackend import CBackend
from spy.backend.spy import FQN_FORMAT, SPyBackend
from spy.build.config import BuildConfig, BuildTarget, OutputKind
from spy.doppler import ErrorMode
from spy.errors import SPyError
from spy.highlight import highlight_src
from spy.magic_py_parse import magic_py_parse
from spy.textbuilder import Color
from spy.util import (
    cleanup_spyc_files,
    colors_coordinates,
    format_colors_as_json,
)
from spy.vendored.dataclass_typer import dataclass_typer
from spy.vm.b import B
from spy.vm.debugger.spdb import SPdb
from spy.vm.function import W_ASTFunc, W_FuncType
from spy.vm.module import W_Module
from spy.vm.vm import SPyVM

app = typer.Typer(pretty_exceptions_enable=False)


@dataclass
class Arguments:
    filename: Annotated[
        Optional[Path],
        Argument(help=""),
    ] = None

    execute: Annotated[
        bool,
        Option(
            "-x",
            "--execute",
            help="Execute the file (default)",
        ),
    ] = False

    pyparse: Annotated[
        bool,
        Option("-P", "--pyparse", help="Dump the Python AST"),
    ] = False

    parse: Annotated[
        bool,
        Option("-p", "--parse", help="Dump the SPy AST"),
    ] = False

    colorize: Annotated[
        bool,
        Option(
            "-C",
            "--colorize",
            help="Output the pre-redshifted AST with blue / red text colors.",
        ),
    ] = False

    format: Annotated[
        str,
        Option(
            "--format",
            help="Output format for --colorize (ansi or json)",
            click_type=click.Choice(["ansi", "json"]),
        ),
    ] = "ansi"

    imports: Annotated[
        bool,
        Option("-I", "--imports", help="Dump the (recursive) list of imports"),
    ] = False

    symtable: Annotated[
        bool,
        Option("-S", "--symtable", help="Dump the symtables"),
    ] = False

    redshift: Annotated[
        bool,
        Option(
            "-r",
            "--redshift",
            help="Perform redshift and dump the result",
        ),
    ] = False

    cwrite: Annotated[
        bool,
        Option("--cwrite", help="Generate the C code"),
    ] = False

    cdump: Annotated[
        bool,
        Option("--cdump", help="Dump the generated C code to stdout"),
    ] = False

    compile: Annotated[
        bool,
        Option("-c", "--compile", help="Compile the generated C code"),
    ] = False

    build_dir: Annotated[
        Optional[Path],
        Option(
            "-b",
            "--build-dir",
            help="Directory to store generated files (defaults to build/ next to the "
            ".spy file)",
        ),
    ] = None

    opt_level: Annotated[
        int,
        Option(
            "-O",
            metavar="LEVEL",
            help="Optimization level",
        ),
    ] = 0

    debug_symbols: Annotated[
        bool,
        Option("-g", help="Generate debug symbols"),
    ] = False

    release_mode: Annotated[
        bool,
        Option("--release", help="enable release mode"),
    ] = False

    target: Annotated[
        BuildTarget,
        Option(
            "-t",
            "--target",
            help="Compilation target",
            click_type=click.Choice(BuildTarget.__args__),
        ),
    ] = "native"

    output_kind: Annotated[
        OutputKind,
        Option(
            "-k",
            "--output-kind",
            help="Output kind",
            click_type=click.Choice(OutputKind.__args__),
        ),
    ] = "exe"

    error_mode: Annotated[
        ErrorMode,
        Option(
            "-E",
            "--error-mode",
            help="Handling strategy for static errors",
            click_type=click.Choice(ErrorMode.__args__),
        ),
    ] = "eager"

    full_fqn: Annotated[
        bool,
        Option("--full-fqn", help="Show full FQNs in redshifted modules"),
    ] = False

    timeit: Annotated[
        bool,
        Option("--timeit", help="Print execution time"),
    ] = False

    pdb: Annotated[
        bool,
        Option("--pdb", help="Enter interp-level debugger in case of error"),
    ] = False

    spdb: Annotated[
        bool,
        Option("--spdb", help="Enter app-level debugger in case of error"),
    ] = False

    cleanup: Annotated[
        bool,
        Option(
            "--cleanup", help="Remove all .spyc cache files from vm.path directories"
        ),
    ] = False

    no_spyc: Annotated[
        bool,
        Option("--no-spyc", help="Disable loading/saving of .spyc cache files"),
    ] = False

    def __post_init__(self) -> None:
        self.validate_actions()

        # Validate filename based on action
        if self.cleanup:
            # For cleanup, filename must be None or an existing directory
            if self.filename is not None and not self.filename.is_dir():
                raise typer.BadParameter(
                    f"--cleanup requires a directory argument, but {self.filename} is not a directory"
                )
        else:
            # For other actions, filename is required and must be a file
            if self.filename is None:
                raise typer.BadParameter("FILENAME is required")
            elif not self.filename.exists():
                raise typer.BadParameter(f"File {self.filename} does not exist")

    def validate_actions(self) -> None:
        # check that we specify at most one of the following options
        possible_actions = [
            "execute",
            "pyparse",
            "parse",
            "imports",
            "symtable",
            "redshift",
            "cwrite",
            "compile",
            "colorize",
            "cleanup",
        ]
        actions = {a for a in possible_actions if getattr(self, a)}
        n = len(actions)
        if n == 0:
            self.execute = True
        elif n == 1:
            pass  # this is valid
        elif (
            actions == {"redshift", "execute"}
            or actions == {"redshift", "parse"}
            or actions == {"colorize", "parse"}
        ):
            pass  # these are valid
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
    fqn_format: FQN_FORMAT = "full" if full_fqn else "short"
    b = SPyBackend(vm, fqn_format=fqn_format)
    spy_code = b.dump_mod(modname)
    print(highlight_src("spy", spy_code))


def dump_spy_mod_ast(vm: SPyVM, modname: str) -> None:
    for fqn, w_obj in vm.fqns_by_modname(modname):
        if isinstance(w_obj, W_ASTFunc) and w_obj.color == "red" and w_obj.fqn == fqn:
            print(f"`{fqn}` = ", end="")
            w_obj.funcdef.pp()
            print()


def pyproject_entry_point() -> Any:
    """
    This is called by the script generated by pyproject.toml
    """
    if sys.platform == "emscripten":
        print(
            "The 'spy' command does not work in a pyodide venv running under node. "
            "Please use python -m spy"
        )
        sys.exit(1)
    return app()


@app.command()
@dataclass_typer
def main(args: Arguments) -> None:
    # this is the main Typer entry point
    if sys.platform == "emscripten":
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


GLOBAL_VM: Optional[SPyVM] = None


async def real_main(args: Arguments) -> None:
    """
    A wrapper around inner_main, to catch/display SPy errors and to
    implement --pdb
    """
    try:
        return await inner_main(args)
    except SPyError as e:
        ## traceback.print_exc()
        ## print()

        # special case SPdbQuit
        if e.etype == "W_SPdbQuit":
            print("SPdbQuit")
            sys.exit(1)

        print(e.format(use_colors=True))

        if args.spdb:
            # post-mortem applevel debugger
            assert GLOBAL_VM is not None
            w_tb = e.w_exc.w_tb
            assert w_tb is not None
            spdb = SPdb(GLOBAL_VM, w_tb)
            spdb.post_mortem()
        elif args.pdb:
            # post-mortem interp-level debugger
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
    print(Color.set("yellow", "[warning] "), end="")
    print(err.format())


def get_build_dir(args: Arguments) -> py.path.local:
    if args.build_dir is not None:
        build_dir = args.build_dir
    else:
        assert args.filename is not None
        srcdir = args.filename.parent
        build_dir = srcdir / "build"

    # print(f"Build dir:    {build_dir}")
    build_dir.mkdir(exist_ok=True, parents=True)
    return py.path.local(str(build_dir))


async def inner_main(args: Arguments) -> None:
    """
    The actual code for the spy executable
    """
    global GLOBAL_VM

    # Handle cleanup early, before any import/execution logic
    if args.cleanup:
        path = args.filename if args.filename is not None else Path(os.getcwd())
        cleanup_spyc_files(py.path.local(path), verbose=True)
        return

    # All other commands require a filename
    assert args.filename is not None

    if args.pyparse:
        do_pyparse(str(args.filename))
        return

    if args.filename.suffix == ".py":
        print(
            f"Error: {args.filename} is a .py file, not a .spy file.", file=sys.stderr
        )
        sys.exit(1)

    modname = args.filename.stem
    srcdir = args.filename.parent
    vm = await SPyVM.async_new()

    GLOBAL_VM = vm

    vm.robust_import_caching = True  # don't raise if .spyc are unreadable/invalid

    vm.path.append(str(srcdir))
    if args.error_mode == "warn":
        args.error_mode = "lazy"
        vm.emit_warning = emit_warning

    importer = ImportAnalyzer(vm, modname, use_spyc=not args.no_spyc)
    importer.parse_all()

    orig_mod = importer.getmod(modname)
    if args.parse and not args.redshift and not args.colorize:
        orig_mod.pp()
        return

    if args.imports:
        importer.pp()
        return

    if args.symtable:
        scopes = importer.analyze_one(modname, orig_mod)
        scopes.pp()
        return

    importer.import_all()
    w_mod = vm.modules_w[modname]

    if args.execute and not args.redshift:
        execute_spy_main(args, vm, w_mod)
        return

    if args.colorize:
        # Signal to the redshift codde that we want to retain expr color information
        vm.ast_color_map = {}
    vm.redshift(error_mode=args.error_mode)
    # vm.pp_globals()
    # vm.pp_modules()

    if args.redshift or args.colorize:
        if args.execute:
            execute_spy_main(args, vm, w_mod)
        elif args.colorize:
            if args.parse:
                # --colorize shows us the pre-redshifted AST, with the colors detected by redshifting
                orig_mod.pp(vm=vm)
            else:
                coords = colors_coordinates(orig_mod, vm.ast_color_map)
                if args.format == "json":
                    print(format_colors_as_json(coords))
                else:
                    print(colorize_sourcecode(args.filename, coords))
        elif args.parse:
            dump_spy_mod_ast(vm, modname)
        else:
            dump_spy_mod(vm, modname, args.full_fqn)
        return

    config = BuildConfig(
        target=args.target,
        kind=args.output_kind,
        build_type="release" if args.release_mode else "debug",
    )

    cwd = py.path.local(".")
    build_dir = get_build_dir(args)
    dump_c = args.cwrite and args.cdump
    backend = CBackend(vm, modname, config, build_dir, dump_c=dump_c)

    backend.cwrite()
    backend.write_build_script()
    assert backend.build_script is not None

    if args.cwrite:
        cfiles = ", ".join([f.relto(cwd) for f in backend.cfiles])
        build_script = backend.build_script.relto(cwd)
        print(f"C files:      {cfiles}")
        print(f"Build script: {build_script}")
        return

    outfile = backend.build()
    executable = outfile.relto(cwd)
    if executable == "":
        # outfile is not in a subdir of cwd, let's display the full path
        executable = str(outfile)
    print(f"[{config.build_type}] {executable} ")


def execute_spy_main(args: Arguments, vm: SPyVM, w_mod: W_Module) -> None:
    w_main_functype = W_FuncType.parse("def() -> None")
    w_main = w_mod.getattr_maybe("main")
    if w_main is None:
        print("Cannot find function main()")
        return

    vm.typecheck(w_main, w_main_functype)
    assert isinstance(w_main, W_ASTFunc)

    # find the redshifted version, if necessary
    if args.redshift:
        assert not w_main.is_valid
        assert w_main.w_redshifted_into is not None
        w_main = w_main.w_redshifted_into
        assert w_main.redshifted
    else:
        assert not w_main.redshifted

    a = time.time()
    w_res = vm.fast_call(w_main, [])
    b = time.time()
    if args.timeit:
        print(f"main(): {b - a:.3f} seconds", file=sys.stderr)
    assert w_res is B.w_None


def colorize_sourcecode(sourcefile: Path, coords_dict: dict) -> str:
    reset = "\033[0m"
    ansi_colors = {"red": "\033[41m\033[30m", "blue": "\033[44m\033[30m"}
    with open(sourcefile) as f:
        lines = f.readlines()

    highlighted_lines = []

    for i, line in enumerate(lines, start=1):
        if i not in coords_dict:
            highlighted_lines.append(line)
            continue

        # Segments in input order: later spans overwrite earlier ones
        spans = [
            (int(s.split(":")[0]), int(s.split(":")[1]), color)
            for s, color in coords_dict[i]
        ]

        # Track color per character using segments
        line_len = len(line)
        color_map = [None] * line_len
        for start, end, color in spans:
            for j in range(start, min(end + 1, line_len)):
                color_map[j] = color

        # Build line from contiguous segments
        result = []
        current_color = None
        cursor = 0
        while cursor < line_len:
            c = color_map[cursor]
            if c != current_color:
                if current_color is not None:
                    result.append(reset)
                if c is not None:
                    # Find contiguous run of this color
                    run_end = cursor
                    while run_end < line_len and color_map[run_end] == c:
                        run_end += 1
                    result.append(ansi_colors[c] + line[cursor:run_end] + reset)
                    cursor = run_end
                    current_color = None
                    continue
                current_color = c
            else:
                result.append(line[cursor])
            cursor += 1

        highlighted_lines.append("".join(result))
    return "".join(
        highlight_src("spy", line.rstrip("\n")) + "\n" for line in highlighted_lines
    )
