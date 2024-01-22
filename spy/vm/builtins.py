"""
Builtins module.

Note that this contains only the "basic" builtins (i.e., all the primitive types
and constants which are used everywhere).

There are additional builtins in builtins2.py -- which is super ugly but it's an easy workaround to avoid circular imports
"""

from typing import Optional
from spy.fqn import FQN
from spy.vm.object import w_DynamicType, W_Object, W_Type, W_void, W_i32, W_bool
from spy.vm.str import W_str
from spy.vm.function import W_FuncType, W_BuiltinFunc

class B:
    w_object = W_Object._w
    w_type = W_Type._w
    w_dynamic = w_DynamicType
    w_i32 = W_i32._w
    w_bool = W_bool._w
    w_void = W_void._w
    w_str = W_str._w
    w_None = W_void._w_singleton
    w_True = W_bool._w_singleton_True
    w_False = W_bool._w_singleton_False

    @classmethod
    def lookup(cls, name: str) -> Optional[W_Object]:
        attr = 'w_' + name
        return getattr(cls, attr, None)
