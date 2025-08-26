from typing import TYPE_CHECKING, Any
from spy.vm.b import B
from spy.vm.primitive import W_I32, W_Dynamic
from spy.vm.object import (W_Object)
from spy.vm.builtin import builtin_method
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

@B.builtin_type('tuple')
class W_Tuple(W_Object):
    """
    This is not the "real" tuple type that we will have in SPy.

    It's a trimmed-down "dynamic" tuple, which can contain an arbitrary number
    of items of arbitrary types. It is meant to be used in blue code, and we
    need it to bootstrap SPy.

    Eventally, it will become a "real" type-safe, generic type.
    """
    __spy_storage_category__ = 'value'

    items_w: list[W_Object]

    def __init__(self, items_w: list[W_Object]) -> None:
        self.items_w = items_w

    def spy_unwrap(self, vm: 'SPyVM') -> tuple:
        return tuple([vm.unwrap(w_item) for w_item in self.items_w])

    def spy_key(self, vm: 'SPyVM') -> Any:
        return tuple(w_item.spy_key(vm) for w_item in self.items_w)

    @builtin_method('__getitem__')
    @staticmethod
    def w_getitem(vm: 'SPyVM', w_tup: 'W_Tuple', w_i: W_I32) -> W_Dynamic:
        i = vm.unwrap_i32(w_i)
        # XXX bound check?
        return w_tup.items_w[i]
