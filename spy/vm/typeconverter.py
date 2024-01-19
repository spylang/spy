from typing import TYPE_CHECKING
from dataclasses import dataclass
from spy.vm.object import W_Object, W_Type
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

@dataclass
class TypeConverter:
    """
    Base class to represent a type conversion step.
    """
    w_type: W_Type # the desired type after the conversion

    def convert(self, vm: 'SPyVM', w_obj: W_Object) -> W_Object:
        """
        Convert w_obj to the desired type.

        The invariant is that the result of convert() must pass a
        vm.typecheck(..., self.w_type) check.
        """
        raise NotImplementedError


class DynamicCast(TypeConverter):
    """
    This doesn't actually perform any active "conversion", it just checks at
    runtime that the given object is an instance of the desired type.
    """

    def convert(self, vm: 'SPyVM', w_obj: W_Object) -> W_Object:
        vm.typecheck(w_obj, self.w_type)
        return w_obj
