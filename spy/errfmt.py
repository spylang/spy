from typing import Literal, TYPE_CHECKING
from dataclasses import dataclass
import linecache
from spy.location import Loc
from spy.textbuilder import ColorFormatter

if TYPE_CHECKING:
    from spy.vm.exc import W_Exception

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

    def emit_message(self, level: Level, message: str) -> None:
        prefix = self.color.set(level, level)
        message = self.color.set('default', message)
        self.w(f'{prefix}: {message}')

    def emit_annotation(self, ann: Annotation) -> None:
        filename = ann.loc.filename
        line = ann.loc.line_start
        col = ann.loc.col_start + 1  # Loc columns are 0-based but we want 1-based
        srcline = linecache.getline(filename, line).rstrip('\n')
        carets = self.make_carets(srcline, ann.loc, ann.message)
        carets = self.color.set(ann.level, carets)
        self.w(f'   --> {filename}:{line}:{col}')
        self.w(f'{line:>3} | {srcline}')
        self.w(f'    | {carets}')
        self.w('')

    def make_carets(self, srcline: str, loc: Loc, message: str) -> str:
        a = loc.col_start
        b = loc.col_end
        if b < 0:
            b = len(srcline) + b + 1
        n = b-a
        line = ' ' * a + '^' * n
        return line + ' ' + message
