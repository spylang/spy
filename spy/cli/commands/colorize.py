from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import click
from typer import Option

import spy.ast
from spy.analyze.importing import ImportAnalyzer
from spy.backend.html import SpyastJs
from spy.doppler import ErrorMode

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM
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


def colorize_mod(
    vm: "SPyVM", modname: str, *, use_spyc: bool, error_mode: ErrorMode
) -> "spy.ast.Module":
    """
    Import and redshift the given module, populating vm.ast_color_map.
    Return the original (pre-redshift) AST module.
    """
    importer = ImportAnalyzer(vm, modname, use_spyc=use_spyc)
    importer.parse_all()
    orig_mod = importer.getmod(modname)
    importer.import_all()
    vm.ast_color_map = {}
    vm.redshift(error_mode=error_mode)
    return orig_mod


async def colorize(args: Colorize_Args) -> None:
    """Output the redshifted code or AST with blue / red text colors."""
    modname = args.filename.stem
    vm = await init_vm(args)

    orig_mod = colorize_mod(
        vm, modname, use_spyc=not args.no_spyc, error_mode=args.error_mode
    )
    coords = colors_coordinates(orig_mod, vm.ast_color_map)

    if args.format == "ast":
        orig_mod.pp(vm=vm)
    elif args.format == "json":
        print(format_colors_as_json(coords))
    elif args.format == "spy":
        print(colorize_sourcecode(args.filename, coords), end="")
    elif args.format == "html":
        assert vm.ast_color_map is not None
        html = dump_colorize_html(orig_mod, vm.ast_color_map, args.spyast_js)
        build_dir = Path(args.filename.parent) / "build"
        build_dir.mkdir(exist_ok=True, parents=True)
        out = build_dir / f"{modname}_colorize.html"
        out.write_text(html)
        print(f"Written {out}")
    else:
        assert False, "unreachable format choice"
