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
