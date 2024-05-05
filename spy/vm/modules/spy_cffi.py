from typing import TYPE_CHECKING
import struct
from spy.vm.b import B
from spy.vm.object import spytype, Member, Annotated
from spy.vm.w import W_Func, W_Type, W_Object, W_I32, W_F64, W_Void, W_Str
from spy.vm.registry import ModuleRegistry
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

SPY_CFFI = CFFI = ModuleRegistry('spy_cffi', '<spy_cffi>')

@spytype('Field')
class W_Field(W_Object):
    w_name: Annotated[W_Str, Member('name')]
    w_offset: Annotated[W_I32, Member('offset')]
    w_type: Annotated[W_Type, Member('type')]

    @staticmethod
    def spy_new(vm: 'SPyVM', w_cls: W_Type, w_name: W_Str,
                w_offset: W_I32, w_type: W_Type) -> 'W_Field':
        w_field = W_Field()
        w_field.w_name = w_name
        w_field.w_offset = w_offset
        w_field.w_type = w_type
        return w_field

CFFI.add('Field', W_Field._w)
