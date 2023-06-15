import linecache
import spy.ast

def make_carets(loc: spy.ast.Location) -> str:
    a = loc.col_start
    b = loc.col_end
    n = b-a
    return ' ' * a + '^' * n

def format_full_error(filename: str, loc: spy.ast.Location, msg: str) -> str:
    """
    Format an error message to display to the user, including the source code,
    and visual hints to highlight which part of the line we are referring to.
    """
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
    loc: spy.ast.Location

    def __init__(self, filename: str, loc: spy.ast.Location, msg: str) -> None:
        self.filename = filename
        self.loc = loc
        self.msg = msg
        fullmsg = format_full_error(filename, loc, msg)
        super().__init__(fullmsg)


class SPyParseError(SPyCompileError):
    pass
