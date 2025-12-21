from dataclasses import dataclass
from typing import Annotated

import click
from typer import Option

from spy.analyze.importing import ImportAnalyzer
from spy.cli._format import colorize_sourcecode
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
            help="Output format for color data (ansi, json, or spy [source])",
            click_type=click.Choice(["ast", "json", "spy"]),
        ),
    ] = "spy"


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
    else:
        assert False, "unreachable format choice"
