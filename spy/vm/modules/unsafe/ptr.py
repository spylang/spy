from typing import TYPE_CHECKING, ClassVar
import fixedint
from spy.errors import SPyPanicError
from spy.fqn import QN
from spy.vm.b import B
from spy.vm.object import spytype
from spy.vm.w import W_Object, W_I32, W_Type, W_Void, W_Str, W_Dynamic
from spy.vm.opimpl import W_OpImpl, W_Value
from spy.vm.sig import spy_builtin
from . import UNSAFE
from .misc import sizeof
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM




@UNSAFE.spytype('ptr')
class W_Ptr(W_Object):
    __spy_storage_category__ = 'value'

    # XXX: this works only if we target 32bit platforms such as wasm32, but we
    # need to think of a more general solution
    addr: fixedint.Int32
    length: fixedint.Int32 # how many items in the array

    def __init__(self, addr: int | fixedint.Int32,
                 length: int | fixedint.Int32) -> None:
        assert type(addr) in (int, fixedint.Int32)
        assert type(length) in (int, fixedint.Int32)
        assert length >= 1
        self.addr = fixedint.Int32(addr)
        self.length = fixedint.Int32(length)

    def __repr__(self) -> str:
        clsname = self.__class__.__name__
        return f'{clsname}(0x{self.addr:x}, length={self.length})'

    @staticmethod
    def meta_op_GETITEM(vm: 'SPyVM', wv_p: W_Value, wv_i: W_Value) -> W_OpImpl:
        return W_OpImpl.simple(vm.wrap_func(make_ptr_type))

    def spy_unwrap(self, vm: 'SPyVM') -> fixedint.Int32:
        return self.addr



@UNSAFE.builtin(color='blue')
def make_ptr_type(vm: 'SPyVM', w_cls: W_Object, w_T: W_Type) -> W_Object:
    from .struct import W_StructType
    assert w_cls is vm.wrap(W_Ptr)

    T = w_T.pyclass
    app_name = f'ptr[{w_T.name}]'         # e.g. ptr[i32]
    interp_name = f'W_Ptr[{T.__name__}]'  # e.g. W_Ptr[W_I32]
    ITEMSIZE = sizeof(w_T)

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

        @staticmethod
        def op_GETATTR(vm: 'SPyVM', wv_ptr: W_Value,
                       wv_attr: W_Value) -> W_OpImpl:
            # getattr is supported only on ptr-to-structs
            if not w_T.is_struct():
                return W_OpImpl.NULL

            assert isinstance(w_T, W_StructType)
            attr = wv_attr.blue_unwrap_str(vm)
            if attr not in w_T.fields:
                XXX
                # raise AttributeError

            w_field_T = w_T.fields[attr]
            offset = w_T.offsets[attr]
            # XXX it would be better to have a more official API to create
            # "constant" W_Values. Here we use i=999 to indicate something which
            # is not in the arglist.
            wv_offset = W_Value.from_w_obj(vm, vm.wrap(offset), 'off', 999)

            # this is basically: ptr_getfield[field_T](ptr, attr, offset)
            my_ptr_getfield = vm.call(UNSAFE.w_ptr_getfield, [w_field_T])
            return W_OpImpl.with_values(
                vm.wrap(my_ptr_getfield),
                [wv_ptr, wv_attr, wv_offset]
            )

        @staticmethod
        def op_SETATTR(vm: 'SPyVM', wv_ptr: W_Value, wv_attr: W_Value,
                       wv_v: W_Value) -> W_OpImpl:
            # setattr is supported only on ptr-to-structs
            if not w_T.is_struct():
                return W_OpImpl.NULL

            assert isinstance(w_T, W_StructType)
            attr = wv_attr.blue_unwrap_str(vm)
            if attr not in w_T.fields:
                XXX
                # raise AttributeError

            w_field_T = w_T.fields[attr]
            offset = w_T.offsets[attr]
            # XXX it would be better to have a more official API to create
            # "constant" W_Values. Here we use i=999 to indicate something which
            # is not in the arglist.
            wv_offset = W_Value.from_w_obj(vm, vm.wrap(offset), 'off', 999)

            # this is basically: ptr_setfield[field_T](ptr, attr, offset, v)
            my_ptr_setfield = vm.call(UNSAFE.w_ptr_setfield, [w_field_T])
            return W_OpImpl.with_values(
                vm.wrap(my_ptr_setfield),
                [wv_ptr, wv_attr, wv_offset, wv_v]
            )


    @spy_builtin(QN(f'unsafe::ptr_{w_T.name}_load'))
    def ptr_load(vm: 'SPyVM', w_ptr: W_MyPtr, w_i: W_I32) -> T:
        base = w_ptr.addr
        length = w_ptr.length
        i = vm.unwrap_i32(w_i)
        addr = base + ITEMSIZE * i
        if i >= length:
            msg = (f"ptr_load out of bounds: 0x{addr:x}[{i}] "
                   f"(upper bound: {length})")
            raise SPyPanicError(msg)
        return read_ptr(vm, addr, w_T)

    @spy_builtin(QN(f'unsafe::ptr_{w_T.name}_store'))
    def ptr_store(vm: 'SPyVM', w_ptr: W_MyPtr,
                  w_i: W_I32, w_v: T) -> W_Void:
        base = w_ptr.addr
        length = w_ptr.length
        i = vm.unwrap_i32(w_i)<xs
        addr = base + ITEMSIZE * i
        if i >= length:
            msg = (f"ptr_store out of bounds: 0x{addr:x}[{i}] "
                   f"(upper bound: {length})")
            raise SPyPanicError(msg)
        write_ptr(vm, addr, w_T, w_v)

    W_MyPtr.__name__ = W_MyPtr.__qualname__ = interp_name
    return vm.wrap(W_MyPtr)



@UNSAFE.builtin(color='blue')
def ptr_getfield(vm: 'SPyVM', w_T: W_Type) -> W_Dynamic:
    T = w_T.pyclass  # W_I32
    t = w_T.name     # 'i32'

    @spy_builtin(QN(f'unsafe::ptr_getfield_{t}'))  # unsafe::ptr_getfield_i32
    def my_ptr_getfield(vm: 'SPyVM', w_ptr: W_Ptr, w_attr: W_Str,
                        w_offset: W_I32) -> T:
        """
        NOTE: w_attr is ignored here, but it's used by the C backend
        """
        addr = w_ptr.addr + vm.unwrap_i32(w_offset)
        return read_ptr(vm, addr, w_T)

    return vm.wrap(my_ptr_getfield)


@UNSAFE.builtin(color='blue')
def ptr_setfield(vm: 'SPyVM', w_T: W_Type) -> W_Dynamic:
    T = w_T.pyclass  # W_I32
    t = w_T.name     # 'i32'

    @spy_builtin(QN(f'unsafe::ptr_setfield_{t}'))  # unsafe::ptr_setfield_i32
    def my_ptr_setfield(vm: 'SPyVM', w_ptr: W_Ptr, w_attr: W_Str,
                        w_offset: W_I32, w_val: T) -> W_Void:
        """
        NOTE: w_attr is ignored here, but it's used by the C backend
        """
        addr = w_ptr.addr + vm.unwrap_i32(w_offset)
        write_ptr(vm, addr, w_T, w_val)

    return vm.wrap(my_ptr_setfield)


def read_ptr(vm: 'SPyVM', addr: fixedint.Int32, w_T: W_Type) -> W_Object:
    if w_T is B.w_i32:
        return vm.wrap(vm.ll.mem.read_i32(addr))
    elif w_T is B.w_f64:
        return vm.wrap(vm.ll.mem.read_f64(addr))
    elif w_T.is_struct():
        return w_T.pyclass(addr)
    else:
        assert False

def write_ptr(vm: 'SPyVM', addr: fixedint.Int32, w_T: W_Type,
              w_val: W_Object) -> None:
    if w_T is B.w_i32:
        v = vm.unwrap_i32(w_val)
        vm.ll.mem.write_i32(addr, v)
    elif w_T is B.w_f64:
        v = vm.unwrap_f64(w_val)
        vm.ll.mem.write_f64(addr, v)
    else:
        assert False