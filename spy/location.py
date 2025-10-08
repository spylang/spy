import sys
import inspect
import linecache
import dataclasses
from dataclasses import dataclass
from typing import Callable, Any

@dataclass(frozen=True)
class Loc:
    """
    Represent a location inside the source code
    """
    filename: str
    line_start: int
    line_end: int
    col_start: int
    col_end: int

    @classmethod
    def here(cls, level: int = -1) -> "Loc":
        """
        Return a Loc corresponding to the interp-level code on the call
        stack.

        By default, level=-1 means "caller's frame".
        level=-2 is "caller of the caller", etc.
        """
        # don't use inspect.stack(), it's horribly slow. Better to get
        # the frames directly. Using inspect.stack() makes the SPy
        # interpreter ~20x slower
        assert level < 0
        f = sys._getframe(-level)
        return cls(
            filename = f.f_code.co_filename,
            line_start = f.f_lineno,
            line_end = f.f_lineno,
            col_start = 0,
            col_end = -1 # whole line
        )

    @classmethod
    def fake(cls) -> "Loc":
        """
        For tests
        """
        return Loc("<fake>", 1, 1, 1, 1)

    @classmethod
    def combine(cls, start: "Loc", end: "Loc") -> "Loc":
        """
        Return a new Loc which spans from 'start' to 'end'
        """
        assert start.filename == end.filename
        l1 = start.line_start
        c1 = start.col_start
        l2 = end.line_end
        c2 = end.col_end
        return cls(start.filename, l1, l2, c1, c2)

    @classmethod
    def from_pyfunc(cls, pyfunc: Callable) -> "Loc":
        # in case of decorators, start points to the line with the first
        # decorator. Try to find the actual 'def'
        lines, start = inspect.getsourcelines(pyfunc)
        for i, l in enumerate(lines):
            if l.strip().startswith("def "):
                start = start + i
                break
        return cls(
            filename = inspect.getfile(pyfunc),
            line_start = start,
            line_end = start,
            col_start = 0,
            col_end = -1 # whole line
        )

    def replace(self, **kwargs: Any) -> "Loc":
        return dataclasses.replace(self, **kwargs)

    def make_end_loc(self) -> "Loc":
        """
        Return a new Loc which starts where this one ends
        """
        return self.replace(line_start=self.line_end,
                            col_start=self.col_end)

    def __repr__(self) -> str:
        l1 = self.line_start
        c1 = self.col_start
        l2 = self.line_end
        c2 = self.col_end
        if l1 == l2 == c1 == c2 == 0:
            return f"<Loc: '{self.filename}'>"
        else:
            return f"<Loc: '{self.filename} {l1}:{c1} {l2}:{c2}'>"

    def get_src(self) -> str:
        """
        Return the piece of source code pointed by this Loc
        """
        filename = self.filename
        if self.line_start == self.line_end:
            # Single line case
            line = self.line_start
            a = self.col_start
            b = self.col_end
            srcline = linecache.getline(filename, line)
            return srcline[a:b]
        else:
            # Multi-line case
            lines = []
            for line_num in range(self.line_start, self.line_end + 1):
                srcline = linecache.getline(filename, line_num)
                if line_num == self.line_start:
                    # First line - start from col_start
                    lines.append(srcline[self.col_start:])
                elif line_num == self.line_end:
                    # Last line - end at col_end
                    lines.append(srcline[:self.col_end])
                else:
                    # Middle lines - include whole line
                    lines.append(srcline)
            return "".join(lines)

    def pp(self) -> None:
        """
        Visualize the piece of code which correspond to this Loc
        """
        from spy.errfmt import ErrorFormatter, Annotation
        fmt = ErrorFormatter(use_colors=True) # type: ignore
        ann = Annotation("note", "", self)
        fmt.emit_annotation(ann)
        print(fmt.build())
