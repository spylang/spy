"""
Builtins module.

Note that this contains only the "basic" builtins (i.e., all the primitive types
and constants which are used everywhere).

There are additional builtins in builtins2.py -- which is super ugly but it's an easy workaround to avoid circular imports
"""

from typing import Optional, TYPE_CHECKING
from spy.fqn import FQN
from spy.vm.object import w_DynamicType, W_Object, W_Type, W_void, W_i32, W_bool
from spy.vm.str import W_str
from spy.vm.function import W_FuncType, W_BuiltinFunc
from spy.vm.registry import ModuleRegistry

B = ModuleRegistry('builtins', '<builtins>')

B.add('object', W_Object._w)
B.add('type', W_Type._w)
B.add('dynamic', w_DynamicType)
B.add('i32', W_i32._w)
B.add('bool', W_bool._w)
B.add('void', W_void._w)
B.add('str', W_str._w)
B.add('None', W_void._w_singleton)
B.add('True', W_bool._w_singleton_True)
B.add('False', W_bool._w_singleton_False)
