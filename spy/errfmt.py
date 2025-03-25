from typing import Literal, TYPE_CHECKING
from dataclasses import dataclass
import linecache
from spy.location import Loc
from spy.textbuilder import ColorFormatter

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
        self.color.note = self.color.green # type: ignore
        self.lines = []

    def w(self, s: str) -> None:
        self.lines.append(s)

    def build(self) -> str:
        return '\n'.join(self.lines)

    def emit_message(self, level: Level, etype: str, message: str) -> None:
        prefix = self.color.set(level, etype)
        message = self.color.set('default', message)
        self.w(f'{prefix}: {message}')

    def emit_annotation(self, ann: Annotation) -> None:
        filename = ann.loc.filename
        line = ann.loc.line_start
        col = ann.loc.col_start + 1 # Loc columns are 0-based but we want 1-based
        srcline = linecache.getline(filename, line).rstrip('\n')
        underline = self.make_underline(srcline, ann.loc, ann.message)
        underline = self.color.set(ann.level, underline)
        self.w(f'   --> {filename}:{line}:{col}')
        self.w(f'{line:>3} | {srcline}')
        self.w(f'    | {underline}')
        self.w('')

    def make_underline(self, srcline: str, loc: Loc, message: str) -> str:
        a = loc.col_start
        b = loc.col_end
        if b < 0:
            b = len(srcline) + b + 1
        n = b-a
        # these are various ways to visually display underlines.
        if n < 2:
            underline = '^' * max(n, 1)
        else:
            #underline = '^' * (n-2)
            #underline = '└' + '─'*(n-2) + '┴───►'
            #underline = '└' + '─'*(n-2) + '┘'
            #underline = '+' + '-'*(n-2) + '+'
            #underline = '^' + '-'*(n-2) + '^'
            underline = '|' + '_'*(n-2) + '|'
        line = ' ' * a + underline
        return line + ' ' + message
