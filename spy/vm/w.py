"""
This is just to make it easier to import all the various W_* classes
"""

from spy.vm.builtin import builtin_type
from spy.vm.function import W_ASTFunc, W_BuiltinFunc, W_Func, W_FuncType
from spy.vm.interp_list import W_InterpList
from spy.vm.module import W_Module
from spy.vm.object import W_Object, W_Type
from spy.vm.opspec import W_OpSpec
from spy.vm.primitive import W_F64, W_I32, W_Bool, W_Dynamic, W_NoneType
from spy.vm.str import W_Str
