from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import click
from typer import Option

from spy.analyze.importing import ImportAnalyzer
from spy.backend.html import HTMLBackend, SpyastJs
from spy.backend.spy import AST_FORMAT, SPyBackend
from spy.cli._format import dump_spy_mod, dump_spy_mod_ast
from spy.cli._runners import init_vm
from spy.cli.commands.shared_args import (
    Base_Args,
    Filename_Required_Args,
)
from spy.highlight import highlight_src


@dataclass
class _astcompile_mixin:
    format: Annotated[
        str,
        Option(
            "--format",
            "-f",
            help="Output format (ast, spy [source], or html)",
            click_type=click.Choice(["ast", "spy", "html"]),
        ),
    ] = "ast"

    full_ast: Annotated[
        bool,
        Option(
            "--full-ast", help="Show full AST node types (e.g., LocalDirect, OuterCell)"
        ),
    ] = False

    spyast_js: Annotated[
        SpyastJs,
        Option(
            "--spyast-js",
            help="How to include spyast.js in the HTML output",
            click_type=click.Choice(["cdn", "inline"]),
        ),
    ] = "inline"


@dataclass
class ASTCompile_Args(Base_Args, _astcompile_mixin, Filename_Required_Args): ...


async def astcompile(args: ASTCompile_Args) -> None:
    """Dump the astcompiled SPy AST"""
    modname = args.filename.stem
    vm = await init_vm(args)

    importer = ImportAnalyzer(vm, modname, use_spyc=not args.no_spyc)
    importer.astcompile_all()
    mod = importer.getmod(modname)

    if args.format == "ast":
        mod.pp()
    elif args.format == "spy":
        ast_format: AST_FORMAT = "full" if args.full_ast else "short"
        b = SPyBackend(vm, ast_format=ast_format)
        b.modname = modname
        for decl in mod.decls:
            b.emit_decl(decl)
            b.out.wl()
        print(highlight_src("spy", b.out.build().rstrip()))
    elif args.format == "html":
        hb = HTMLBackend(args.spyast_js)
        html = hb.generate([(modname, mod)])
        build_dir = Path(args.filename.parent) / "build"
        build_dir.mkdir(exist_ok=True, parents=True)
        out = build_dir / f"{modname}_astcompile.html"
        out.write_text(html)
        print(f"Written {out}")
    else:
        assert False, f"Invalid astcompile format `{args.format}`"
