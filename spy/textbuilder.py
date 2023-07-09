from typing import Optional, Iterator
from contextlib import contextmanager

class TextBuilder:
    level: int  # indentation level
    lines: list[str]
    use_colors: bool

    def __init__(self, *, use_colors: bool = False) -> None:
        self.level = 0
        self.lines = ['']
        self.color = ColorFormatter(use_colors)

    @contextmanager
    def indent(self) -> Iterator[None]:
        self.level += 1
        yield
        self.level -= 1

    def write(self, s: str, *, color: Optional[str] = None) -> None:
        s = self.color.set(color, s)
        if self.lines[-1] == '':
            # add the indentation
            spaces = ' ' * (self.level * 4)
            self.lines[-1] = spaces
        self.lines[-1] += s

    def writeline(self, s: str = '', *, color: Optional[str] = None) -> None:
        self.write(s, color=color)
        self.lines.append('')

    # shortcuts
    w = write
    wl = writeline

    def build(self) -> str:
        return '\n'.join(self.lines)


class ColorFormatter:
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
