import linecache
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from spy.location import Loc
from spy.textbuilder import ColorFormatter, TextBuilder

if TYPE_CHECKING:
    from spy.vm.exc import W_Traceback

Level = Literal["error", "note", "panic"]


@dataclass
class Annotation:
    level: Level
    message: str
    loc: Loc


class ErrorFormatter:
    out: TextBuilder

    def __init__(self, use_colors: bool) -> None:
        self.out = TextBuilder(use_colors=use_colors)
        # add "custom colors" to ColorFormatter, so that we can do
        # self.color.set('error', 'hello')
        self.out.fmt.error = ColorFormatter.red  # type: ignore
        self.out.fmt.panic = ColorFormatter.red  # type: ignore
        self.out.fmt.note = ColorFormatter.green  # type: ignore

    def build(self) -> str:
        return self.out.build()

    def emit_traceback(self, w_tb: "W_Traceback") -> None:
        self.out.wl("Traceback (most recent call last):")
        for e in w_tb.entries:
            if e.kind == "astframe":
                funcname = str(e.func)
            elif e.kind == "modframe":
                funcname = f"[module] {e.func}"
            elif e.kind == "classframe":
                funcname = f"[classdef] {e.func}"
            elif e.kind == "dopplerframe":
                funcname = f"[redshift] {e.func}"
            else:
                assert False, f"invalid frame kind: {e.kind}"
            self.emit_loc(e.loc, funcname=funcname, color="error")
        self.out.wl()

    def emit_message(self, level: Level, etype: str, message: str) -> None:
        prefix = self.out.fmt.set(level, etype)
        self.out.wl(f"{prefix}: {message}")

    def emit_annotation(self, ann: Annotation) -> None:
        self.emit_loc(ann.loc, funcname=ann.level, message=ann.message, color=ann.level)
        self.out.wl()

    def emit_loc(
        self,
        loc: Loc,
        *,
        funcname: str = "",
        message: str = "",
        color: str = "default",
    ) -> None:
        filename = loc.filename
        line = loc.line_start
        col = loc.col_start + 1  # Loc columns are 0-based but we want 1-based
        srcline = linecache.getline(filename, line).rstrip("\n")
        underline = self.make_underline(srcline, loc, message)
        underline = self.out.fmt.set(color, underline)

        if funcname == "":
            header = f"--> {filename}:{line}"
        else:
            funcname = self.out.fmt.set("yellow", funcname)
            header = f"{funcname} at {filename}:{line}"

        self.out.wl(f"  * {header}")
        self.out.wl(f"  | {srcline}")
        # self.out.wl(f"{line:>3} | {srcline}")
        self.out.wl(f"  | {underline}")

    def make_underline(self, srcline: str, loc: Loc, message: str) -> str:
        a = loc.col_start
        b = loc.col_end
        if b < 0:
            b = len(srcline) + b + 1
        n = b - a
        # these are various ways to visually display underlines.
        if n <= 2:
            underline = "^" * max(n, 1)
        else:
            # underline = '^' * (n-2)
            # underline = '└' + '─'*(n-2) + '┴───►'
            # underline = '└' + '─'*(n-2) + '┘'
            # underline = '+' + '-'*(n-2) + '+'
            # underline = '^' + '-'*(n-2) + '^'
            underline = "|" + "_" * (n - 2) + "|"
        line = " " * a + underline
        return line + " " + message
