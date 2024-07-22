from typing import TYPE_CHECKING
import struct
from spy.fqn import QN
from spy.vm.b import B
from spy.vm.object import spytype, Member, Annotated
from spy.vm.w import (W_Func, W_Type, W_Object, W_I32, W_F64, W_Void, W_Str,
                      W_Dynamic)
from spy.vm.sig import spy_builtin
from spy.vm.function import W_Func
from spy.vm.list import make_W_List
from spy.vm.registry import ModuleRegistry

from spy.vm.modules.types import W_TypeDef

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

JSFFI = ModuleRegistry('jsffi', '<jsffi>')

@JSFFI.builtin
def debug(vm: 'SPyVM', w_str: W_Str) -> None:
    s = vm.unwrap_str(w_str)
    print('[JSFFI debug]', s)
