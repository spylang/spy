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

    def replace(self, **kwargs: int) -> 'Loc':
        return dataclasses.replace(self, **kwargs)

    def make_end_loc(self) -> 'Loc':
        """
        Return a new Loc which starts where this one ends
        """
        return self.replace(line_start=self.line_end,
                            col_start=self.col_end)

    def __repr__(self):
        l1 = self.line_start
        c1 = self.col_start
        l2 = self.line_end
        c2 = self.col_end
        return f"<Loc: '{self.filename} {l1}:{c1} {l2}:{c2}'>"
