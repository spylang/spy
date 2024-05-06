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
from spy.vm.modules.rawbuffer import (RB, W_RawBuffer, rb_alloc, rb_get_i32,
                                      rb_set_i32)

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

SPY_CFFI = CFFI = ModuleRegistry('spy_cffi', '<spy_cffi>')

CACHE = {}

@spytype('Field')
class W_Field(W_Object):
    w_name: Annotated[W_Str, Member('name')]
    w_offset: Annotated[W_I32, Member('offset')]
    w_type: Annotated[W_Type, Member('type')]

    w_get: Annotated[W_Func, Member('__GET__')]
    w_set: Annotated[W_Func, Member('__SET__')]

    @staticmethod
    def spy_new(vm: 'SPyVM', w_cls: W_Type, w_name: W_Str,
                w_offset: W_I32, w_type: W_Type,
                w_get: W_Func, w_set: W_Func) -> 'W_Field':
        w_field = W_Field()
        w_field.w_name = w_name
        w_field.w_offset = w_offset
        w_field.w_type = w_type
        w_field.w_get = w_get
        w_field.w_set = w_set
        return w_field


W_List__W_Field = make_W_List(None, W_Field._w) # XXX



@CFFI.builtin
def new_StructType(vm: 'SPyVM', w_name: W_Str,
                   w_fields: W_List__W_Field) -> W_Type:

    name = vm.unwrap_str(w_name)
    size = 8 # XXX compute size

    @spytype(f'Meta_{name}')
    class W_StructType(W_TypeDef):

        @staticmethod
        def op_CALL(vm: 'SPyVM', w_type: W_Type,
                    w_argtypes: W_Dynamic) -> W_Dynamic:

            @spy_builtin(QN("xxx::new")) # XXX
            def new(vm: 'SPyVM', w_class: W_Type) -> W_RawBuffer:
                w_rb = rb_alloc(vm, vm.wrap(size))
                return w_rb

            return vm.wrap(new)

    w_result = W_StructType(vm, name, RB.w_RawBuffer, w_fields)
    return w_result

CFFI.add('Field', W_Field._w)
