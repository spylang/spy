from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import click
from typer import Option

from spy.analyze.importing import ImportAnalyzer
from spy.cli._runners import init_vm
from spy.cli.commands.shared_args import (
    Base_Args,
    Filename_Required_Args,
)
from spy.tool.astviz import SpyastJs, generate_html


@dataclass
class _parse_mixin:
    format: Annotated[
        str,
        Option(
            "--format",
            help="Output format (ast or html)",
            click_type=click.Choice(["ast", "html"]),
        ),
    ] = "ast"

    spyast_js: Annotated[
        SpyastJs,
        Option(
            "--spyast-js",
            help="How to include spyast.js in the HTML output",
            click_type=click.Choice(["cdn", "inline"]),
        ),
    ] = "cdn"


@dataclass
class Parse_Args(Base_Args, _parse_mixin, Filename_Required_Args): ...


async def parse(args: Parse_Args) -> None:
    """Dump the SPy AST"""
    modname = args.filename.stem
    vm = await init_vm(args)

    importer = ImportAnalyzer(vm, modname, use_spyc=not args.no_spyc)
    importer.parse_all()

    orig_mod = importer.getmod(modname)

    if args.format == "ast":
        orig_mod.pp()
    elif args.format == "html":
        html = generate_html([(modname, orig_mod)], args.spyast_js)
        build_dir = Path(args.filename.parent) / "build"
        build_dir.mkdir(exist_ok=True, parents=True)
        out = build_dir / f"{modname}_ast.html"
        out.write_text(html)
        print(f"Written {out}")
    else:
        assert False, f"Invalid parse format `{args.format}`"
