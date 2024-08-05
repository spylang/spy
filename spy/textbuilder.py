from typing import Optional, Iterator, Union
import textwrap
from contextlib import contextmanager

class TextBuilder:
    level: int  # indentation level
    lines: list[Union[str, 'TextBuilder']]
    use_colors: bool

    def __init__(self, *, use_colors: bool = False) -> None:
        self.level = 0
        self.lines = ['']
        self.use_colors = use_colors
        self.color = ColorFormatter(use_colors)

    @property
    def lineno(self) -> int:
        """
        XXX this is broken in presence of nested builders :(

        Return the number of the CURRENT line.

        The invariant is that if .lineno == N, then .write(), .writeline(),
        etc. will write text on line number N.
        """
        return len(self.lines)

    @contextmanager
    def indent(self) -> Iterator[None]:
        self.level += 1
        yield
        self.level -= 1

    def make_nested_builder(self) -> 'TextBuilder':
        """
        Create a new nested TextBuilder, at the current position.

        The nested builder can be written independently of the outer one, and
        it will be built automatically when the outer is built.
        """
        if self.lines[-1] != '':
            raise ValueError('make_nested_builder can be called only '
                             'after a newline')
        nested = TextBuilder(use_colors=self.use_colors)
        nested.level = self.level
        self.lines[-1] = nested
        self.lines.append('')
        return nested

    def write(self, s: str, *, color: Optional[str] = None) -> None:
        assert '\n' not in s
        assert isinstance(self.lines[-1], str)
        s = self.color.set(color, s)
        if self.lines[-1] == '':
            # add the indentation
            spaces = ' ' * (self.level * 4)
            self.lines[-1] = spaces
        self.lines[-1] += s

    def writeline(self, s: str = '', *, color: Optional[str] = None) -> None:
        self.write(s, color=color)
        self.lines.append('')

    def writeblock(self, s: str, *, color: Optional[str] = None) -> None:
        s = textwrap.dedent(s).strip()
        for line in s.splitlines():
            self.writeline(line, color=color)

    # shortcuts
    w = write
    wl = writeline
    wb = writeblock

    def build(self) -> str:
        strlines = []
        for line in self.lines:
            if isinstance(line, TextBuilder):
                line = line.build()
                if line == '':
                    continue # nothing to do
                else:
                    assert line.endswith('\n')
                    line = line[:-1]
                    strlines.append(line)
            else:
                strlines.append(line)
        return '\n'.join(strlines)


class ColorFormatter:
    default = '00'
    black = '30'
    darkred = '31'
    darkgreen = '32'
    brown = '33'
    darkblue = '34'
    purple = '35'
    teal = '36'
    lightgray = '37'
    darkgray = '30;01'
    red = '31;01'
    green = '32;01'
    yellow = '33;01'
    blue = '34;01'
    fuchsia = '35;01'
    turquoise = '36;01'
    white = '37;01'

    def __init__(self, use_colors: bool) -> None:
        self._use_colors = use_colors

    def set(self, color: Optional[str], s: str) -> str:
        if color is None or not self._use_colors:
            return s
        try:
            color = getattr(self, color)
        except AttributeError:
            pass
        return '\x1b[%sm%s\x1b[00m' % (color, s)

# create a global instance, so that you can just do Color.set('red', ....)
Color = ColorFormatter(use_colors=True)
