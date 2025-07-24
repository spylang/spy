import re
from typing import Optional, Iterator, Union
import textwrap
from contextlib import contextmanager


class TextBuilder:
    level: int  # indentation level
    lines: list[Union[str, 'TextBuilder']]
    use_colors: bool
    _ansi_escape_re = re.compile(r'\x1b\[[0-9;]*m')

    def __init__(self, *, use_colors: bool = False) -> None:
        self.level = 0
        self.lines = ['']
        self.use_colors = use_colors
        self.color_formatter = ColorFormatter(use_colors)
        self.active_text_color: Optional[str] = None

    def visible_length(self, s: str) -> int:
        return len(self._ansi_escape_re.sub('', s))

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

    @contextmanager
    def color_block(self, text_color: str, reset: bool = True) -> Iterator[None]:
        self.set_color(text_color)
        yield
        if self.use_colors and reset:
            self.writeraw(self.color_formatter.reset)

    def set_color(self, text_color: str) -> None:
        self.writeraw(self.color_formatter.start(text_color))

    def set_active_text_color(self, text_color: str) -> None:
        """Set the active text color for persistent coloring in redshift mode"""
        self.active_text_color = text_color
        self.set_color(text_color)

    def clear_active_text_color(self) -> None:
        """Clear the active text color and reset to no color"""
        self.active_text_color = None
        if self.use_colors:
            self.writeraw(self.color_formatter.reset)

    def make_nested_builder(self, *, detached: bool = False) -> 'TextBuilder':
        """
        Create a new nested TextBuilder.

        If detached==False (the default), the nested builder will
        automatically be placed at the current position.

        If detached==True, the nested builder must be attached later, by
        calling attach_nested_builder.

        The nested builder can be written independently of the outer one, and
        it will be built automatically when the outer is built.
        """
        nested = TextBuilder(use_colors=self.use_colors)
        if not detached:
            self.attach_nested_builder(nested)
        return nested

    def attach_nested_builder(self, nested: 'TextBuilder') -> None:
        """
        Attach a nested builder which was previously created by
        make_nested_builder().

        NOTE: the indentation level will be the one which was active at
        creation time, not attachment time. This is probably a bug, but too
        bad for now.
        See also test_detached_indent.
        """
        if self.lines[-1] != '':
            raise ValueError('attach_nested_builder can be called only '
                             'after a newline')
        nested.level = self.level
        self.lines[-1] = nested
        self.lines.append('')

    def writeraw(self, s: str) -> None:
        """
        Append a string, without any indentation or color formatting.
        """
        assert '\n' not in s
        assert isinstance(self.lines[-1], str)
        self.lines[-1] += s

    def write(self, s: str, *, color: Optional[str] = None) -> None:
        assert '\n' not in s
        assert isinstance(self.lines[-1], str)
        
        # Use active text color if no explicit color is provided
        effective_color = color if color is not None else self.active_text_color
        s = self.color_formatter.set(effective_color, s)
        
        if self.visible_length(self.lines[-1]) == 0:
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
    reset = '\x1b[00m'

    def __init__(self, use_colors: bool) -> None:
        self._use_colors = use_colors

    def start(self, text_color: Optional[str]) -> str:
        """
        Set output to the given color only
        """
        if text_color is None or not self._use_colors:
            return ''
        try:
            text_color = getattr(self, text_color)
        except AttributeError:
            pass
        return '\x1b[%sm' % (text_color)

    def set(self, text_color: Optional[str], s: str = '') -> str:
        """
        Set output to the given color, and print the string s
        """
        if text_color is None or not self._use_colors:
            return s
        try:
            text_color = getattr(self, text_color)
        except AttributeError:
            pass
        return '\x1b[%sm%s\x1b[00m' % (text_color, s)

# create a global instance, so that you can just do Color.set('red', ....)
Color = ColorFormatter(use_colors=True)
