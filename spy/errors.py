import linecache
import ast as py_ast
import spy.ast
from spy.location import Loc


def make_carets(loc: Loc) -> str:
    a = loc.col_start
    b = loc.col_end
    n = b-a
    return ' ' * a + '^' * n

def format_full_error(loc: Loc, msg: str) -> str:
    """
    Format an error message to display to the user, including the source code,
    and visual hints to highlight which part of the line we are referring to.
    """
    filename = loc.filename
    line = loc.line_start
    # Location has 0-based columns, but we want to display 1-based to the
    # user
    col = loc.col_start + 1
    srcline = linecache.getline(filename, line).rstrip('\n')
    lines = [
        f'{filename}:{line}:{col}: error: {msg}',
        srcline,
        make_carets(loc)
    ]
    return '\n'.join(lines)

class SPyCompileError(Exception):
    filename: str
    loc: Loc

    def __init__(self, loc: Loc, msg: str) -> None:
        self.loc = loc
        self.msg = msg
        fullmsg = format_full_error(loc, msg)
        super().__init__(fullmsg)


class SPyParseError(SPyCompileError):
    pass

class SPyTypeError(SPyCompileError):
    pass
