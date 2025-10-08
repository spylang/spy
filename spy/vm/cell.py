from typing import TYPE_CHECKING
from spy.fqn import FQN
from spy.vm.b import TYPES
from spy.vm.object import W_Object

if TYPE_CHECKING:
    pass

@TYPES.builtin_type("Cell")
class W_Cell(W_Object):
    """
    A cell object represent an indirect global reference.

    Each cell has a FQN so it can be uniquely identified after redshifting and
    by the C backend, but its content is red and mutable at runtime.

    See Symbol.storage, ScopeAnalyzer.define_name and
    ASTFrame._specialize_Name.
    """

    def __init__(self, fqn: FQN, w_val: W_Object) -> None:
        self.fqn = fqn
        self._w_val = w_val

    def __repr__(self) -> str:
        return f"<spy cell {self.fqn} = {self._w_val}>"

    def get(self) -> W_Object:
        return self._w_val

    def set(self, w_val: W_Object) -> None:
        self._w_val = w_val
