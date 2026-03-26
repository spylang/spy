from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import click
from typer import Option

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
): ...


async def redshift(args: Redshift_Args) -> None:
    """
    Perform redshift and dump or execute the module
    """

    modname = args.filename.stem
    vm = await init_vm(args)

    importer = ImportAnalyzer(vm, modname, use_spyc=not args.no_spyc)
    importer.parse_all()
    importer.import_all()

    vm.ast_color_map = {}
    vm.redshift(error_mode=args.error_mode)

    if args.execute:
        w_mod = vm.modules_w[modname]
        argv = args.argv or []
        execute_spy_main(vm, w_mod, argv, redshift=True, _timeit=args.timeit)
    else:
        if args.format == "spy":
            dump_spy_mod(vm, modname, args.full_fqn)
        elif args.format == "ast":
            dump_spy_mod_ast(vm, modname)
        elif args.format == "html":
            html = dump_spy_mod_html(vm, modname, args.spyast_js)
            build_dir = Path(args.filename.parent) / "build"
            build_dir.mkdir(exist_ok=True, parents=True)
            out = build_dir / f"{modname}_rs.html"
            out.write_text(html)
            print(f"Written {out}")
        else:
            assert False, f"Invalid redshift format `{args.format}`"
