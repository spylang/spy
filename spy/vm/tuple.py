from typing import TYPE_CHECKING, Any, no_type_check, Optional
from spy.fqn import QN
from spy.vm.primitive import W_I32, W_Bool, W_Void
from spy.vm.object import (W_Object, W_Type, W_Dynamic)
from spy.vm.builtin import builtin_func, builtin_type
from spy.vm.opimpl import W_OpImpl, W_OpArg
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

@builtin_type('builtins', 'tuple')
class W_Tuple(W_Object):
    """
    This is not the "real" tuple type that we will have in SPy.

    It's a trimmed-down "dynamic" tuple, which can contain an arbitrary number
    of items of arbitrary types. It is meant to be used in blue code, and we
    need it to bootstrap SPy.

    Eventally, it will become a "real" type-safe, generic type.
    """

    items_w: list[W_Object]

    def __init__(self, items_w: list[W_Object]) -> None:
        self.items_w = items_w

    def spy_unwrap(self, vm: 'SPyVM') -> tuple:
        return tuple([vm.unwrap(w_item) for w_item in self.items_w])

    @staticmethod
    def op_GETITEM(vm: 'SPyVM', wop_obj: W_OpArg,
                   wop_i: W_OpArg) -> W_OpImpl:
        return W_OpImpl(w_tuple_getitem)



@builtin_func('operator')
def w_tuple_getitem(vm: 'SPyVM', w_tup: W_Tuple, w_i: W_I32) -> W_Dynamic:
    i = vm.unwrap_i32(w_i)
    # XXX bound check?
    return w_tup.items_w[i]
