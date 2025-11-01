import linecache
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from spy.location import Loc
from spy.textbuilder import ColorFormatter

if TYPE_CHECKING:
    from spy.vm.exc import W_Traceback

Level = Literal["error", "note", "panic"]


@dataclass
class Annotation:
    level: Level
    message: str
    loc: Loc


class ErrorFormatter:
    lines: list[str]

    def __init__(self, use_colors: bool) -> None:
        self.color = ColorFormatter(use_colors)
        # add "custom colors" to ColorFormatter, so that we can do
        # self.color.set('error', 'hello')
        self.color.error = self.color.red  # type: ignore
        self.color.panic = self.color.red  # type: ignore
        self.color.note = self.color.green  # type: ignore
        self.lines = []

    def w(self, s: str) -> None:
        self.lines.append(s)

    def build(self) -> str:
        return "\n".join(self.lines)

    def emit_traceback(self, w_tb: "W_Traceback") -> None:
        self.w("Traceback (most recent call last):")
        for e in w_tb.entries:
            if e.kind == "astframe":
                funcname = str(e.func)
            elif e.kind == "modframe":
                funcname = f"[module] {e.func}"
            elif e.kind == "classframe":
                funcname = f"[classdef] {e.func}"
            elif e.kind == "dopplerframe":
                funcname = f"[redshift] {e.func}"
            self.emit_loc(e.loc, funcname=funcname, color="error")
        self.w("")

    def emit_message(self, level: Level, etype: str, message: str) -> None:
        prefix = self.color.set(level, etype)
        message = self.color.set("default", message)
        self.w(f"{prefix}: {message}")

    def emit_annotation(self, ann: Annotation) -> None:
        self.emit_loc(ann.loc, funcname=ann.level, message=ann.message, color=ann.level)
        self.w("")

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
        underline = self.color.set(color, underline)

        if funcname == "":
            header = f"--> {filename}:{line}"
        else:
            funcname = self.color.set("yellow", funcname)
            header = f"{funcname} at {filename}:{line}"

        self.w(f"  * {header}")
        self.w(f"  | {srcline}")
        # self.w(f"{line:>3} | {srcline}")
        self.w(f"  | {underline}")

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
