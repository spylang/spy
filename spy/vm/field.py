from typing import TYPE_CHECKING, Any
from spy.vm.b import TYPES
from spy.vm.object import W_Type, W_Object
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@TYPES.builtin_type("Field")
class W_Field(W_Object):
    __spy_storage_category__ = "value"

    def __init__(self, name: str, w_T: W_Type) -> None:
        self.name = name
        self.w_T = w_T

    def spy_key(self, vm: "SPyVM") -> Any:
        return ("Field", self.name, self.w_T.spy_key(vm))

    def __repr__(self) -> str:
        return f"<spy field {self.name}: `{self.w_T.fqn.human_name}`>"
