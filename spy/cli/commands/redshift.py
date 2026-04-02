from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Optional

import click
from typer import Argument, Option

from spy.analyze.importing import ImportAnalyzer
from spy.backend.html import SpyastJs
from spy.cli._format import dump_spy_mod, dump_spy_mod_ast, dump_spy_mod_html
from spy.cli._runners import execute_spy_main, init_vm
from spy.cli.commands.shared_args import (
    Base_Args,
    Filename_Required_Args,
    _execute_flag,
    _execute_options,
)


@dataclass
class _redshift_mixin:
    full_fqn: Annotated[
        bool,
        Option("--full-fqn", help="Show full FQNs in redshifted modules"),
    ] = False

    format: Annotated[
        str,
        Option(
            "--format",
            "-f",
            help="Output format (ast, spy [source], or html)",
            click_type=click.Choice(["ast", "spy", "html"]),
        ),
    ] = "spy"

    spyast_js: Annotated[
        SpyastJs,
        Option(
            "--spyast-js",
            help="How to include spyast.js in the HTML output",
            click_type=click.Choice(["cdn", "inline"]),
        ),
    ] = "inline"


@dataclass
class Redshift_Args(
    Base_Args, _redshift_mixin, _execute_flag, _execute_options, Filename_Required_Args
):
    extra_dump: Annotated[
        Optional[list[Path]],
        Option("--dump", help="Additional modules to dump"),
    ] = None


async def redshift(args: Redshift_Args) -> None:
    """
    Perform redshift and dump or execute the module
    """

    modname = args.filename.stem
    vm = await init_vm(args)

    extra_files = args.extra_dump or []
    extra_modnames = [f.stem for f in extra_files]

    for extra_file in extra_files:
        srcdir = str(extra_file.parent)
        if srcdir not in vm.path:
            vm.path.append(srcdir)

    importer = ImportAnalyzer(vm, modname, use_spyc=not args.no_spyc)
    for extra_modname in extra_modnames:
        importer.queue.append(extra_modname)
    importer.parse_all()
    importer.import_all()

    vm.ast_color_map = {}
    vm.redshift(error_mode=args.error_mode)

    if args.execute:
        w_mod = vm.modules_w[modname]
        argv = [str(args.filename)] + (args.argv or [])
        execute_spy_main(vm, w_mod, argv, redshift=True, _timeit=args.timeit)
    else:
        all_files = [args.filename] + extra_files
        all_modnames = [modname] + extra_modnames
        show_filename = len(all_modnames) > 1
        for filename, mod_name in zip(all_files, all_modnames):
            if show_filename and args.format in ("spy", "ast"):
                print(f"# {filename}")
            if args.format == "spy":
                dump_spy_mod(vm, mod_name, args.full_fqn)
            elif args.format == "ast":
                dump_spy_mod_ast(vm, mod_name)
            elif args.format == "html":
                html = dump_spy_mod_html(vm, mod_name, args.spyast_js)
                build_dir = Path(filename.parent) / "build"
                build_dir.mkdir(exist_ok=True, parents=True)
                out = build_dir / f"{mod_name}_rs.html"
                out.write_text(html)
                print(f"Written {out}")
            else:
                assert False, f"Invalid redshift format `{args.format}`"
