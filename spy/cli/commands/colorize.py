from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import click
from typer import Option

from spy.analyze.importing import ImportAnalyzer
from spy.backend.html import SpyastJs
from spy.cli._format import colorize_sourcecode, dump_colorize_html
from spy.cli._runners import init_vm
from spy.cli.commands.shared_args import (
    Base_Args,
    Filename_Required_Args,
)
from spy.util import (
    colors_coordinates,
    format_colors_as_json,
)


@dataclass
class _colorize_mixin:
    format: Annotated[
        str,
        Option(
            "--format",
            "-f",
            help="Output format for color data (ast, json, spy [source], or html)",
            click_type=click.Choice(["ast", "json", "spy", "html"]),
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
class Colorize_Args(Base_Args, _colorize_mixin, Filename_Required_Args): ...


async def colorize(args: Colorize_Args) -> None:
    """Output the redshifted code or AST with blue / red text colors."""
    modname = args.filename.stem
    vm = await init_vm(args)

    importer = ImportAnalyzer(vm, modname, use_spyc=not args.no_spyc)
    importer.parse_all()

    orig_mod = importer.getmod(modname)

    importer.import_all()
    vm.ast_color_map = {}
    vm.redshift(error_mode=args.error_mode)
    coords = colors_coordinates(orig_mod, vm.ast_color_map)

    if args.format == "ast":
        orig_mod.pp(vm=vm)
    elif args.format == "json":
        print(format_colors_as_json(coords))
    elif args.format == "spy":
        print(colorize_sourcecode(args.filename, coords))
    elif args.format == "html":
        html = dump_colorize_html(orig_mod, vm.ast_color_map, args.spyast_js)
        build_dir = Path(args.filename.parent) / "build"
        build_dir.mkdir(exist_ok=True, parents=True)
        out = build_dir / f"{modname}_colorize.html"
        out.write_text(html)
        print(f"Written {out}")
    else:
        assert False, "unreachable format choice"
