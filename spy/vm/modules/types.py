"""
SPy `types` module.

Note that TYPES is defined in spy.vm.b, and that there are other builtin types
which are attached to it here and there (e.g. W_Module and W_Cell).
"""

from typing import TYPE_CHECKING, Any

from spy.location import Loc
from spy.vm.b import TYPES
from spy.vm.builtin import builtin_method, builtin_property
from spy.vm.object import W_Object
from spy.vm.primitive import W_I32
from spy.vm.str import W_Str

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

    @builtin_method("__repr__")
    @staticmethod
    def w_repr(vm: "SPyVM", w_self: "W_Loc") -> W_Str:
        return vm.wrap(repr(w_self.loc))

    @builtin_property("filename")
    @staticmethod
    def w_get_filename(vm: "SPyVM", w_self: "W_Loc") -> W_Str:
        return vm.wrap(w_self.loc.filename)

    @builtin_property("line_start")
    @staticmethod
    def w_get_line_start(vm: "SPyVM", w_self: "W_Loc") -> W_I32:
        return vm.wrap(w_self.loc.line_start)

    @builtin_property("line_end")
    @staticmethod
    def w_get_line_end(vm: "SPyVM", w_self: "W_Loc") -> W_I32:
        return vm.wrap(w_self.loc.line_end)

    @builtin_property("col_start")
    @staticmethod
    def w_get_col_start(vm: "SPyVM", w_self: "W_Loc") -> W_I32:
        return vm.wrap(w_self.loc.col_start)

    @builtin_property("col_end")
    @staticmethod
    def w_get_col_end(vm: "SPyVM", w_self: "W_Loc") -> W_I32:
        return vm.wrap(w_self.loc.col_end)
