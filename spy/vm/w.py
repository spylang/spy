"""
This is just to make it easier to import all the various W_* classes
"""

from spy.vm.function import W_Func, W_FuncType, W_ASTFunc, W_BuiltinFunc
from spy.vm.module import W_Module
from spy.vm.object import (W_Bool, W_F64, W_I32, W_Object, W_Type, W_Void,
                           W_Dynamic)
from spy.vm.str import W_Str
