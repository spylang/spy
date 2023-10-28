import typing
from spy.fqn import FQN
from spy.vm.module import W_Module
from spy.vm.function import W_BuiltinFunction, W_FunctionType
if typing.TYPE_CHECKING:
    from spy.vm.vm import SPyVM


def make(vm: 'SPyVM') -> W_Module:
    from spy.vm.vm import Builtins as B
    w_mod = W_Module(vm, 'testmod')
    w_double = W_BuiltinFunction(
        fqn = FQN('testmod::double'),
        w_functype = W_FunctionType.make(x=B.w_i32, w_restype=B.w_i32),
    )
    vm.register_module(w_mod)
    vm.add_global(FQN('testmod::double'),
                  w_double.w_functype,
                  w_double)
    return w_mod
