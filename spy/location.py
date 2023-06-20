import dataclasses
from dataclasses import dataclass
import ast as py_ast

@dataclass
class Loc:
    """
    Represent a location inside the source code
    """
    line_start: int
    line_end: int
    col_start: int
    col_end: int

    def replace(self, **kwargs: int) -> 'Loc':
        return dataclasses.replace(self, **kwargs)
