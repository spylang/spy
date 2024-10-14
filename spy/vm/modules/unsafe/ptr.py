from typing import TYPE_CHECKING, ClassVar
import fixedint
from spy.fqn import QN
from spy.vm.b import B
from spy.vm.object import spytype
from spy.vm.w import W_Object, W_I32, W_Type, W_Void
from spy.vm.opimpl import W_OpImpl, W_Value
from spy.vm.sig import spy_builtin
from . import UNSAFE
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@UNSAFE.spytype('ptr')
class W_Ptr(W_Object):
    __spy_storage_category__ = 'value'

    # XXX: this works only if we target 32bit platforms such as wasm32, but we
    # need to think of a more general solution
    addr: fixedint.Int32

    def __init__(self, addr: int | fixedint.Int32) -> None:
        assert type(addr) in (int, fixedint.Int32)
        self.addr = fixedint.Int32(addr)

    def __repr__(self) -> str:
        clsname = self.__class__.__name__
        return f'{clsname}(0x{self.addr:x})'

    @staticmethod
    def meta_op_GETITEM(vm: 'SPyVM', wv_p: W_Value, wv_i: W_Value) -> W_OpImpl:
        return W_OpImpl.simple(vm.wrap_func(make_ptr_type))

    def spy_unwrap(self, vm: 'SPyVM') -> fixedint.Int32:
        return self.addr



@UNSAFE.builtin(color='blue')
def make_ptr_type(vm: 'SPyVM', w_cls: W_Object, w_T: W_Type) -> W_Object:
    assert w_cls is vm.wrap(W_Ptr)
    assert w_T is B.w_i32 # hardcoded for now

    T = w_T.pyclass
    app_name = f'ptr[{w_T.name}]'         # e.g. ptr[i32]
    interp_name = f'W_Ptr[{T.__name__}]'  # e.g. W_Ptr[W_I32]

    @spytype(app_name)
    class W_MyPtr(W_Ptr):
        w_itemtype: ClassVar[W_Type] = w_T

        @staticmethod
        def op_GETITEM(vm: 'SPyVM', wv_ptr: W_Value, wv_i: W_Value) -> W_OpImpl:
            return W_OpImpl.simple(vm.wrap(ptr_load))

        @staticmethod
        def op_SETITEM(vm: 'SPyVM', wv_ptr: W_Value, wv_i: W_Value,
                       wv_v: W_Value) -> W_OpImpl:
            return W_OpImpl.simple(vm.wrap(ptr_store))


    @spy_builtin(QN('unsafe::i32_ptr_load'))
    def ptr_load(vm: 'SPyVM', w_ptr: W_MyPtr, w_i: W_I32) -> W_I32:
        base = w_ptr.addr
        i = vm.unwrap_i32(w_i)
        # XXX we should introduce bound check
        addr = base + 4*i # XXX item size?
        return vm.wrap(vm.ll.mem.read_i32(addr))

    @spy_builtin(QN('unsafe::i32_ptr_store'))
    def ptr_store(vm: 'SPyVM', w_ptr: W_MyPtr, w_i: W_I32, w_v: W_I32) -> W_Void:
        base = w_ptr.addr
        i = vm.unwrap_i32(w_i)
        v = vm.unwrap_i32(w_v)
        # XXX we should introduce bound check
        addr = base + 4*i # XXX item size?
        vm.ll.mem.write_i32(addr, v)


    W_MyPtr.__name__ = W_MyPtr.__qualname__ = interp_name
    return vm.wrap(W_MyPtr)
