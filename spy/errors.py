from typing import Optional, Literal
from dataclasses import dataclass
import linecache
import spy.ast
from spy.location import Loc
from spy.textbuilder import ColorFormatter

Level = Literal["error", "note"]

def maybe_plural(n: int, singular: str, plural: Optional[str] = None) -> str:
    if n == 1:
        return singular
    elif plural is None:
        return singular + 's'
    else:
        return plural

@dataclass
class Annotation:
    level: Level
    message: str
    loc: Loc


class ErrorFormatter:
    err: 'SPyCompileError'
    lines: list[str]

    def __init__(self, err: 'SPyCompileError', use_colors: bool) -> None:
        self.err = err
        self.color = ColorFormatter(use_colors)
        # add "custom colors" to ColorFormatter, so that we can do
        # self.color.set('error', 'hello')
        self.color.error = self.color.red  # type: ignore
        self.color.note = self.color.green # type: ignore
        self.lines = []

    def w(self, s: str) -> None:
        self.lines.append(s)

    def build(self) -> str:
        return '\n'.join(self.lines)

    def emit_message(self, level: Level, message: str) -> None:
        prefix = self.color.set(level, level)
        message = self.color.set('white', message)
        self.w(f'{prefix}: {message}')

    def emit_annotation(self, ann: Annotation) -> None:
        filename = ann.loc.filename
        line = ann.loc.line_start
        col = ann.loc.col_start + 1  # Loc columns are 0-based but we want 1-based
        srcline = linecache.getline(filename, line).rstrip('\n')
        carets = self.make_carets(ann.loc, ann.message)
        carets = self.color.set(ann.level, carets)
        self.w(f'   --> {filename}:{line}:{col}')
        self.w(f'{line:>3} | {srcline}')
        self.w(f'    | {carets}')
        self.w('')

    def make_carets(self, loc: Loc, message: str) -> str:
        a = loc.col_start
        b = loc.col_end
        n = b-a
        line = ' ' * a + '^' * n
        return line + ' ' + message


class SPyCompileError(Exception):
    message: str
    annotations: list[Annotation]

    def __init__(self, message: str) -> None:
        self.message = message
        self.annotations = []
        super().__init__(message)

    @classmethod
    def simple(cls, primary: str, secondary: str, loc: Loc) -> 'SPyCompileError':
        err = cls(primary)
        err.add('error', secondary, loc)
        return err

    def __str__(self) -> str:
        return self.format(use_colors=False)

    def add(self, level: Level, message: str, loc: Loc) -> None:
        self.annotations.append(Annotation(level, message, loc))

    def format(self, use_colors: bool = True) -> str:
        fmt = ErrorFormatter(self, use_colors)
        fmt.emit_message('error', self.message)
        for ann in self.annotations:
            fmt.emit_annotation(ann)
        return fmt.build()


class SPyParseError(SPyCompileError):
    pass


class SPyTypeError(SPyCompileError):
    pass


class SPyLookupError(SPyCompileError):
    pass


# ======

class SPyRuntimeError(Exception):
    pass

class SPyRuntimeAbort(SPyRuntimeError):
    pass
