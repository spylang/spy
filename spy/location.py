import dataclasses
from dataclasses import dataclass
import linecache

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
    def fake(cls) -> 'Loc':
        """
        For tests
        """
        return Loc('<fake>', 1, 1, 1, 1)

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
