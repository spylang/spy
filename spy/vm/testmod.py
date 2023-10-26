import typing
from spy.vm.module import W_Module
from spy.vm.function import W_BuiltinFunction, W_FunctionType
if typing.TYPE_CHECKING:
    from spy.vm.vm import SPyVM


def make(vm: 'SPyVM') -> W_Module:
    from spy.vm.vm import Builtins as B
    w_mod = W_Module(vm, 'testmod')
    w_double = W_BuiltinFunction(
        name = 'double',
        llname = 'spy_testmod_double',
        w_functype = W_FunctionType.make(x=B.w_i32, w_restype=B.w_i32),
    )
    w_mod.add('double', w_double, w_type=None)
    return w_mod
