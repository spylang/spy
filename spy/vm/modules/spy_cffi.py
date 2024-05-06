from typing import TYPE_CHECKING
import struct
from spy.fqn import QN
from spy.vm.b import B
from spy.vm.object import spytype, Member, Annotated
from spy.vm.w import (W_Func, W_Type, W_Object, W_I32, W_F64, W_Void, W_Str,
                      W_Dynamic)
from spy.vm.sig import spy_builtin
from spy.vm.list import make_W_List
from spy.vm.registry import ModuleRegistry

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

    @staticmethod
    def spy_new(vm: 'SPyVM', w_cls: W_Type, w_name: W_Str,
                w_offset: W_I32, w_type: W_Type) -> 'W_Field':
        w_field = W_Field()
        w_field.w_name = w_name
        w_field.w_offset = w_offset
        w_field.w_type = w_type
        return w_field

    def op_GET(self, vm: 'SPyVM', w_T: W_Type, w_attr: W_Str) -> W_Dynamic:
        key = (vm, id(self), 'get')
        if key in CACHE:
            return CACHE[key]

        T = w_T.pyclass
        R = self.w_type.pyclass
        w_offset = self.w_offset
        name = vm.unwrap_str(self.w_name)

        @spy_builtin(QN(f"spy_cffi::get_{name}"))
        def opimpl(vm: 'SPyVM', w_obj: T, w_attr: W_Str) -> R:
            return rb_get_i32(vm, w_obj, w_offset)

        w_opimpl = vm.wrap(opimpl)
        CACHE[key] = w_opimpl
        return w_opimpl

    def op_SET(self, vm: 'SPyVM', w_T: W_Type, w_attr: W_Str,
               w_V: W_Type) -> W_Dynamic:
        key = (vm, id(self), 'set')
        if key in CACHE:
            return CACHE[key]

        assert w_V is self.w_type
        T = w_T.pyclass
        V = w_V.pyclass
        w_offset = self.w_offset
        name = vm.unwrap_str(self.w_name)

        @spy_builtin(QN(f"spy_cffi::set_{name}"))
        def opimpl(vm: 'SPyVM', w_obj: T, w_attr: W_Str, w_val: V) -> None:
            rb_set_i32(vm, w_obj, w_offset, w_val)

        w_opimpl = vm.wrap(opimpl)
        CACHE[key] = w_opimpl
        return w_opimpl


W_List__W_Field = make_W_List(None, W_Field._w) # XXX



## @CFFI.builtin
## def new_StructType(vm: 'SPyVM', w_name: W_Str,
##                    w_fields: W_List__W_Field) -> W_Type:

##     name = vm.unwrap_str(w_name)
##     size = 8 # XXX compute size

##     @spytype(name)
##     class W_StructObject(W_Object):
##         w_rb: W_RawBuffer

##         def __init__(self, w_rb: W_RawBuffer) -> None:
##             self.w_rb = w_rb

##         @staticmethod
##         def spy_new(vm: 'SPyVM', w_cls: W_Type) -> f'W_{name}':
##             w_rb = rb_alloc(vm, vm.wrap(size))
##             return W_StructObject(w_rb)


##     W_StructObject.__name__ = f'W_{name}'
##     W_StructObject.__qualname__ = f'W_{name}'

##     return vm.wrap(W_StructObject)


from spy.vm.modules.types import W_TypeDef

@CFFI.builtin
def new_StructType(vm: 'SPyVM', w_name: W_Str,
                   w_fields: W_List__W_Field) -> W_Type:

    name = vm.unwrap_str(w_name)
    size = 8 # XXX compute size

    ## class W_StructObject(W_Object):
    ##     w_rb: W_RawBuffer

    ##     def __init__(self, w_rb: W_RawBuffer) -> None:
    ##         self.w_rb = w_rb

    ##     @staticmethod
    ##     def spy_new(vm: 'SPyVM', w_cls: W_Type) -> f'W_{name}':
    ##         w_rb = rb_alloc(vm, vm.wrap(size))
    ##         return W_StructObject(w_rb)


    ## W_StructObject.__name__ = f'W_{name}'
    ## W_StructObject.__qualname__ = f'W_{name}'

    ## return vm.wrap(W_StructObject)

    @spytype('MetaPoint') # ???
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
