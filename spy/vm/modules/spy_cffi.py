from typing import TYPE_CHECKING
import struct
from spy.vm.b import B
from spy.vm.object import spytype, Member, Annotated
from spy.vm.w import W_Func, W_Type, W_Object, W_I32, W_F64, W_Void, W_Str
from spy.vm.list import make_W_List
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

W_List__W_Field = make_W_List(None, W_Field._w) # XXX

@spytype('StructType')
class W_StructType(W_Type):
    w_name: Annotated[W_Str, Member('name')]
    w_fields: Annotated[W_List__W_Field, Member('fields')]

    @staticmethod
    def spy_new(vm: 'SPyVM', w_cls: W_Type,
                w_name: W_Str,
                w_fields: W_List__W_Field
                ) -> 'W_StructType':
        name = vm.unwrap_str(w_name)

        class W_StructObject(W_Object):
            __qualname__ = f'W_{name}'
        W_StructObject.__name__ = f'W_{name}'

        w_st = W_StructType(name, W_StructObject)
        w_st.w_name = w_name
        w_st.w_fields = w_fields
        W_StructObject._w = w_st

        return w_st





CFFI.add('Field', W_Field._w)
CFFI.add('StructType', W_StructType._w)
