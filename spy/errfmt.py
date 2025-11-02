import linecache
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from spy.location import Loc
from spy.textbuilder import ColorFormatter, TextBuilder

if TYPE_CHECKING:
    from spy.vm.exc import W_Exception, W_Traceback

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

    @classmethod
    def format_exception(cls, w_exc: "W_Exception", *, use_colors: bool) -> str:
        fmt = cls(use_colors)
        fmt.emit_exception(w_exc)
        return fmt.build()

    def build(self) -> str:
        return self.out.build()

    def emit_exception(self, w_exc: "W_Exception") -> None:
        if w_exc.w_tb:
            self.emit_traceback(w_exc.w_tb)
        etype = w_exc.__class__.__name__[2:]
        prefix = self.out.fmt.set("error", etype)
        self.out.wl(f"{prefix}: {w_exc.message}")
        for ann in w_exc.annotations:
            self.emit_annotation(ann)

    def emit_traceback(self, w_tb: "W_Traceback") -> None:
        if w_tb.entries and w_tb.entries[0].kind == "dopplerframe":
            self.out.wl("Static error during redshift:", color="red")

        self.out.wl(f"Traceback (most recent call last):")
        for e in w_tb.entries:
            if e.kind == "astframe":
                where = str(e.func)
            elif e.kind == "modframe":
                where = f"[module] {e.func}"
            elif e.kind == "classframe":
                where = f"[classdef] {e.func}"
            elif e.kind == "dopplerframe":
                where = f"[redshift] {e.func}"
            else:
                assert False, f"invalid frame kind: {e.kind}"

            where = self.out.fmt.set("purple", where)
            srcline, underline = self.fmt_loc(e.loc, "red", "")
            self.out.wl(f"  * {where} at {e.loc.filename}:{e.loc.line_start}")
            self.out.wl(f"  | {srcline}")
            self.out.wl(f"  | {underline}")

        self.out.wl()

    def emit_annotation(self, ann: Annotation) -> None:
        loc = ann.loc
        srcline, underline = self.fmt_loc(loc, ann.level, ann.message)
        header = f"{loc.filename}:{loc.line_start}"

        self.out.wl(f"  | {header}")
        self.out.wl(f"  | {srcline}")
        self.out.wl(f"  | {underline}")
        self.out.wl()

    def fmt_loc(self, loc: Loc, color: str, message: str) -> tuple[str, str]:
        """
        Take a loc and return (srcline, underline), which are supposed to be printed
        one after the other
        """
        filename = loc.filename
        line = loc.line_start
        col = loc.col_start + 1  # Loc columns are 0-based but we want 1-based
        srcline = linecache.getline(filename, line).rstrip("\n")
        underline = self.make_underline(srcline, loc, message)
        underline = self.out.fmt.set(color, underline)
        return srcline, underline

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
