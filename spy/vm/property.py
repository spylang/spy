from typing import TYPE_CHECKING
from spy.vm.b import BUILTINS
from spy.vm.object import W_Object
from spy.vm.builtin import builtin_method
from spy.vm.function import W_Func

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM
    from spy.vm.opspec import W_MetaArg, W_OpSpec


@BUILTINS.builtin_type('property', lazy_definition=True)
class W_Property(W_Object):

    def __init__(self, w_func: W_Func) -> None:
        self.w_func = w_func

    @builtin_method('__get__', color='blue', kind='metafunc')
    @staticmethod
    def w_GET(vm: 'SPyVM', wam_self: 'W_MetaArg', wam_o: 'W_MetaArg') -> 'W_OpSpec':
        w_prop = wam_self.w_blueval
        assert isinstance(w_prop, W_Property)
        w_func = w_prop.w_func
        return vm.fast_metacall(w_func, [wam_o])
