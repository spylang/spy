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
