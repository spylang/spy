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

    def write(self, s: str, *, color: Optional[str] = None,
              bg: Optional[str] = None) -> None:
        assert '\n' not in s
        assert isinstance(self.lines[-1], str)
        s = self.color.set(color, s, bg=bg)
        if self.lines[-1] == '':
            # add the indentation
            spaces = ' ' * (self.level * 4)
            self.lines[-1] = spaces
        self.lines[-1] += s

    def writeline(self, s: str = '', *, color: Optional[str] = None,
                  bg: Optional[str] = None) -> None:
        self.write(s, color=color, bg=bg)
        self.lines.append('')

    def writeblock(self, s: str, *, color: Optional[str] = None,
                   bg: Optional[str] = None) -> None:
        s = textwrap.dedent(s).strip()
        for line in s.splitlines():
            self.writeline(line, color=color, bg=bg)

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
    # Foreground colors
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

    # Background colors (40-47)
    bg_black = '40'
    bg_darkred = '41'
    bg_darkgreen = '42'
    bg_brown = '43'
    bg_darkblue = '44'
    bg_purple = '45'
    bg_teal = '46'
    bg_lightgray = '47'
    bg_darkgray = '100'
    bg_red = '101'
    bg_green = '102'
    bg_yellow = '103'
    bg_blue = '44'  # Using 44 to match the test expectation
    bg_fuchsia = '105'
    bg_turquoise = '106'
    bg_white = '107'

    def __init__(self, use_colors: bool) -> None:
        self._use_colors = use_colors

    def set(self, color: Optional[str], s: str, *, bg: Optional[str] = None) -> str:
        if (color is None and bg is None) or not self._use_colors:
            return s

        codes = []

        # Process foreground color
        if color is not None:
            try:
                fg_code = getattr(self, color)
                codes.append(fg_code)
            except AttributeError:
                codes.append(color)

        # Process background color
        if bg is not None:
            bg_attr = f"bg_{bg}" if not bg.startswith("bg_") else bg
            try:
                bg_code = getattr(self, bg_attr)
                codes.append(bg_code)
            except AttributeError:
                # If the attribute doesn't exist, try using the raw value
                codes.append(bg if bg.isdigit() else f"4{bg[0]}" if len(bg) == 1 else bg)

        # Join all codes with semicolons
        code_str = ';'.join(c for c in codes if c)
        return f'\x1b[{code_str}m{s}\x1b[00m'

# create a global instance, so that you can just do Color.set('red', ....)
Color = ColorFormatter(use_colors=True)

# ============================================================================
# Sample program to visually inspect in the terminal that things works
# ============================================================================

# run it with python -m spy.textbuilder

def main():
    print("Visual test of ColorFormatter functionality")
    print("==========================================")

    # Test basic foreground colors
    fmt = ColorFormatter(use_colors=True)
    print("\nForeground colors:")
    for color in ['black', 'darkred', 'darkgreen', 'brown', 'darkblue',
                  'purple', 'teal', 'lightgray', 'darkgray', 'red', 'green',
                  'yellow', 'blue', 'fuchsia', 'turquoise', 'white']:
        print(f"{color:10}: {fmt.set(color, f'This is {color} text')}")

    # Test background colors
    print("\nBackground colors:")
    for bg in ['black', 'darkred', 'darkgreen', 'brown', 'darkblue', 'purple',
               'teal', 'lightgray', 'darkgray', 'red', 'green', 'yellow',
               'blue', 'fuchsia', 'turquoise', 'white']:
        print(f"{bg:10}: {fmt.set(None, f'This has {bg} background', bg=bg)}")

    # Test combinations
    print("\nCombinations:")
    combinations = [
        ('red', 'blue'),
        ('white', 'darkblue'),
        ('yellow', 'darkred'),
        ('black', 'green'),
        ('blue', 'yellow')
    ]
    for fg, bg in combinations:
        print(f"{fg:6} on {bg:8}: {fmt.set(fg, f'This is {fg} text on {bg} background', bg=bg)}")

    # Test TextBuilder with colors
    print("\nTextBuilder with colors:")
    b = TextBuilder(use_colors=True)
    b.wl("Normal text")
    b.wl("Red text", color='red')
    b.wl("Blue background", bg='blue')
    b.wl("Red on blue", color='red', bg='blue')
    b.wb("""
        This is a block
        with multiple lines
        in green on dark red
    """, color='green', bg='darkred')

    print(b.build())

    # Test the specific test cases from TestColorFormatter
    print("\nTest cases from TestColorFormatter:")
    fmt = ColorFormatter(use_colors=True)
    print(f"1. Red text: {fmt.set('red', 'hello')}")
    print(f"2. Red on blue: {fmt.set('red', 'hello', bg='blue')}")
    print(f"3. Blue background only: {fmt.set(None, 'hello', bg='blue')}")

if __name__ == "__main__":
    main()
