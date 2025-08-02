from typing import TYPE_CHECKING
from spy.vm.b import BUILTINS
from spy.vm.object import W_Object
from spy.vm.builtin import builtin_method

if TYPE_CHECKING:
    from spy.vm.opspec import W_OpArg, W_OpSpec


@BUILTINS.builtin_type('property', lazy_definition=True)
class W_Property(W_Object):
    __spy_storage_category__ = 'reference'

    def __init__(self, w_func):
        self.w_func = w_func

    @builtin_method('__get__', color='blue', kind='metafunc')
    @staticmethod
    def w_GET(vm: 'SPyVM', wop_self: 'W_OpArg', wop_o: 'W_OpArg') -> 'W_OpSpec':
        w_prop = wop_self.w_blueval
        assert isinstance(w_prop, W_Property)
        w_func = w_prop.w_func
        return vm.fast_metacall(w_func, [wop_o])
