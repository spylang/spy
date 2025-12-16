from dataclasses import dataclass
from pathlib import Path
from typing import (
    Annotated,
    Optional,
)

import click
import py.path
from typer import Option

from spy.analyze.importing import ImportAnalyzer
from spy.backend.c.cbackend import CBackend
from spy.build.config import BuildConfig, BuildTarget, OutputKind
from spy.cli.base_args import (
    General_Args_With_Filename,
)
from spy.cli.support import init_vm


@dataclass
class Build_Args(General_Args_With_Filename):
    cwrite: Annotated[
        bool,
        Option("--cwrite", help="Generate the C code; do not compile"),
    ] = False

    cdump: Annotated[
        bool,
        Option("--cdump", help="Dump the generated C code to stdout; do not compile"),
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


async def build(args: Build_Args) -> None:
    """Compile the generated C code"""
    modname = args.filename.stem
    vm = await init_vm(args)

    importer = ImportAnalyzer(vm, modname)
    importer.parse_all()
    importer.import_all()

    vm.ast_color_map = {}
    vm.redshift(error_mode=args.error_mode)

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


def get_build_dir(args: Build_Args) -> py.path.local:
    if args.build_dir is not None:
        build_dir = args.build_dir
    else:
        assert args.filename is not None
        srcdir = args.filename.parent
        build_dir = srcdir / "build"

    # print(f"Build dir:    {build_dir}")
    build_dir.mkdir(exist_ok=True, parents=True)
    return py.path.local(str(build_dir))
