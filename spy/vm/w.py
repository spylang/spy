"""
This is just to make it easier to import all the various W_* classes
"""

from spy.vm.primitive import W_F64, W_I32, W_Bool, W_Dynamic, W_NoneType
from spy.vm.function import W_Func, W_FuncType, W_ASTFunc, W_BuiltinFunc
from spy.vm.builtin import builtin_func, builtin_type
from spy.vm.module import W_Module
from spy.vm.object import (W_Object, W_Type)
from spy.vm.str import W_Str
from spy.vm.list import W_List
from spy.vm.opimpl import W_OpImpl
