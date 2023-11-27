from typing import Optional
from spy.fqn import FQN
from spy.vm.object import W_Object, W_Type, W_void, W_i32, W_bool
from spy.vm.str import W_str
from spy.vm.function import W_FuncType, W_BuiltinFunc

class B:
    w_object = W_Object._w
    w_type = W_Type._w
    w_i32 = W_i32._w
    w_bool = W_bool._w
    w_void = W_void._w
    w_str = W_str._w
    w_None = W_void._w_singleton
    w_True = W_bool._w_singleton_True
    w_False = W_bool._w_singleton_False

    w_abs = W_BuiltinFunc(
        fqn = FQN('builtins::abs'),
        w_functype = W_FuncType.make(x=w_i32, w_restype=w_i32),
    )

    @classmethod
    def lookup(cls, name: str) -> Optional[W_Object]:
        attr = 'w_' + name
        return getattr(cls, attr, None)
