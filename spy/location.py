import inspect
import dataclasses
from dataclasses import dataclass

@dataclass
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
    def here(cls, level: int = -1) -> 'Loc':
        """
        Return a Loc corresponding to the interp-level code on the call
        stack.

        By default, level=-1 means "caller's frame".
        level=-2 is "caller of the caller", etc.
        """
        assert level < 0
        f = inspect.stack()[-level]
        return cls(
            filename = f.filename,
            line_start = f.lineno,
            line_end = f.lineno,
            col_start = 0,
            col_end = -1 # whole line
        )

    @classmethod
    def fake(cls) -> 'Loc':
        """
        For tests
        """
        return Loc('<fake>', 1, 1, 1, 1)

    @classmethod
    def combine(cls, start: 'Loc', end: 'Loc') -> 'Loc':
        """
        Return a new Loc which spans from 'start' to 'end'
        """
        assert start.filename == end.filename
        l1 = start.line_start
        c1 = start.col_start
        l2 = end.line_end
        c2 = end.col_end
        return cls(start.filename, l1, l2, c1, c2)

    def replace(self, **kwargs: int) -> 'Loc':
        return dataclasses.replace(self, **kwargs)

    def make_end_loc(self) -> 'Loc':
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

    def pp(self) -> None:
        """
        Visualize the piece of code which correspond to this Loc
        """
        from spy.errors import ErrorFormatter, Annotation
        fmt = ErrorFormatter(err=None, use_colors=True) # type: ignore
        ann = Annotation('note', '', self)
        fmt.emit_annotation(ann)
        print(fmt.build())
