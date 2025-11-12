"""
SPy `types` module.

Note that TYPES is defined in spy.vm.b, and that there are other builtin types
which are attached to it here and there (e.g. W_Module and W_Cell).
"""

from typing import TYPE_CHECKING, Any

from spy.location import Loc
from spy.vm.b import TYPES
from spy.vm.object import W_Object

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@TYPES.builtin_type("Loc")
class W_Loc(W_Object):
    """
    Wrapped version of Loc.
    """

    __spy_storage_category__ = "value"

    def __init__(self, loc: Loc) -> None:
        self.loc = loc

    def spy_key(self, vm: "SPyVM") -> Any:
        return ("Loc", self.loc)
