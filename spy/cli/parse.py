from dataclasses import dataclass
from pathlib import Path
from typing import (
    Annotated,
)

import click
from typer import Option

from spy.analyze.importing import ImportAnalyzer
from spy.cli.base_args import (
    Base_Args,
    Filename_Required_Args,
)
from spy.cli.support import init_vm
from spy.util import (
    colors_coordinates,
    format_colors_as_json,
    highlight_src_maybe,
)


@dataclass
class _parse_mixin:
    colorize: Annotated[
        bool,
        Option(
            "-C",
            "--colorize",
            help="Output the pre-redshifted AST with blue / red text colors.",
        ),
    ] = False

    colorize_source: Annotated[
        bool,
        Option(
            "--colorize-source",
            help="Show the original source code, with colors detected by redshifting",
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


@dataclass
class Parse_Args(Base_Args, _parse_mixin, Filename_Required_Args): ...


# TODO rebase and add the --format argument back in


async def parse(args: Parse_Args) -> None:
    """Dump the SPy AST"""
    modname = args.filename.stem
    vm = await init_vm(args)

    importer = ImportAnalyzer(vm, modname)
    importer.parse_all()

    orig_mod = importer.getmod(modname)

    if args.colorize_source:
        importer.import_all()
        vm.ast_color_map = {}
        vm.redshift(error_mode=args.error_mode)
        coords = colors_coordinates(orig_mod, vm.ast_color_map)
        if args.format == "json":
            print(format_colors_as_json(coords))
        else:
            print(highlight_sourcecode(args.filename, coords))
        return

    if not args.colorize:
        orig_mod.pp()
    else:
        orig_mod.pp(vm=vm)


def highlight_sourcecode(sourcefile: Path, coords_dict: dict) -> str:
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
    return "".join(highlight_src_maybe("spy", line) for line in highlighted_lines)
