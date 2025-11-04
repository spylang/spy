"""
Helper functions to implement do_longlist in SPdb.
"""

import linecache
from typing import Any

from spy.location import Loc
from spy.textbuilder import ColorFormatter

CUR_COLOR = "green"
LINENO_COLOR = "turquoise"


def print_longlist(
    loc: Loc, curloc: Loc, *, use_colors: bool = True, file: Any = None
) -> None:
    """
    Print the source code of a function with line numbers, highlighting the current
    location in green.

    Args:
        loc: Location of the whole function (line_start to line_end)
        curloc: Location of the currently executing expression
    """
    color = ColorFormatter(use_colors)
    for line_num in range(loc.line_start, loc.line_end + 1):
        srcline = linecache.getline(loc.filename, line_num).rstrip("\n")
        lineno = color.set("turquoise", f"{line_num:4d}")
        if curloc.line_start <= line_num <= curloc.line_end:
            colored_line = _highlight_line(srcline, curloc, line_num, color)
            print(f"{lineno}  -> {colored_line}", file=file)
        else:
            print(f"{lineno}     {srcline}", file=file)


def _highlight_line(
    srcline: str, curloc: Loc, line_num: int, color: ColorFormatter
) -> str:
    """
    Return a line with the current location highlighted in green.

    Args:
        srcline: The source line to highlight
        curloc: The location to highlight
        line_num: The line number being processed
    """
    if curloc.line_start == curloc.line_end:
        # Single line case - highlight from col_start to col_end
        a = curloc.col_start
        b = curloc.col_end
        if b < 0:
            b = len(srcline) + b + 1

        before = srcline[:a]
        highlighted = srcline[a:b]
        after = srcline[b:]

        return before + color.set(CUR_COLOR, highlighted) + after
    else:
        # Multi-line case
        if line_num == curloc.line_start:
            # First line - highlight from col_start to end of line
            a = curloc.col_start
            before = srcline[:a]
            highlighted = srcline[a:]
            return before + color.set(CUR_COLOR, highlighted)
        elif line_num == curloc.line_end:
            # Last line - highlight from start to col_end
            b = curloc.col_end
            if b < 0:
                b = len(srcline) + b + 1
            highlighted = srcline[:b]
            after = srcline[b:]
            return color.set(CUR_COLOR, highlighted) + after
        else:
            # Middle line - highlight the whole line
            return color.set(CUR_COLOR, srcline)
