from typing import TYPE_CHECKING, ClassVar, Optional, no_type_check
import fixedint
from spy.errors import SPyPanicError
from spy.fqn import QN
from spy.vm.primitive import W_Void
from spy.vm.b import B
from spy.vm.object import spytype
from spy.vm.w import W_Object, W_I32, W_Type, W_Str, W_Dynamic, W_Func
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.builtin import builtin_func
from . import UNSAFE
from .misc import sizeof
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

def hack_hack_fix_typename(t: str) -> str:
    # XXX hack hack hack, it will be fixed when types have a QN and we can
    # properly nest QN qualifiers. In the meantime, we just use W_Type.name, but
    # we  make sure it doesn't contain any square brackets.
    return t.replace('[', '_').replace(']', '')

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
    def meta_op_GETITEM(vm: 'SPyVM', wop_p: W_OpArg,
                        wop_T: W_OpArg) -> W_OpImpl:
        return W_OpImpl(w_make_ptr_type, [wop_T])

    def spy_unwrap(self, vm: 'SPyVM') -> fixedint.Int32:
        return self.addr



@UNSAFE.builtin_func(color='blue')
def w_make_ptr_type(vm: 'SPyVM', w_T: W_Type) -> W_Object:
    from .struct import W_StructType

    T = w_T.pyclass
    app_name = f'ptr[{w_T.name}]'         # e.g. ptr[i32]
    interp_name = f'W_Ptr[{T.__name__}]'  # e.g. W_Ptr[W_I32]
    ITEMSIZE = sizeof(w_T)

    @spytype(app_name)
    class W_MyPtr(W_Ptr):
        w_itemtype: ClassVar[W_Type] = w_T

        @staticmethod
        def op_GETITEM(vm: 'SPyVM', wop_ptr: W_OpArg,
                       wop_i: W_OpArg) -> W_OpImpl:
            return W_OpImpl(w_ptr_load)

        @staticmethod
        def op_SETITEM(vm: 'SPyVM', wop_ptr: W_OpArg, wop_i: W_OpArg,
                       wop_v: W_OpArg) -> W_OpImpl:
            return W_OpImpl(w_ptr_store)

        @staticmethod
        def op_GETATTR(vm: 'SPyVM', wop_ptr: W_OpArg,
                       wop_attr: W_OpArg) -> W_OpImpl:
            return op_ATTR('get', vm, wop_ptr, wop_attr, None)

        @staticmethod
        def op_SETATTR(vm: 'SPyVM', wop_ptr: W_OpArg, wop_attr: W_OpArg,
                       wop_v: W_OpArg) -> W_OpImpl:
            return op_ATTR('set', vm, wop_ptr, wop_attr, wop_v)


    def op_ATTR(opkind: str, vm: 'SPyVM', wop_ptr: W_OpArg, wop_attr: W_OpArg,
                wop_v: Optional[W_OpArg]) -> W_OpImpl:
        """
        Implement both op_GETATTR and op_SETATTR.
        """
        # attributes are supported only on ptr-to-structs
        if not w_T.is_struct(vm):
            return W_OpImpl.NULL

        assert isinstance(w_T, W_StructType)
        attr = wop_attr.blue_unwrap_str(vm)
        if attr not in w_T.fields:
            return W_OpImpl.NULL

        w_field_T = w_T.fields[attr]
        offset = w_T.offsets[attr]
        wop_offset = W_OpArg.const(vm, vm.wrap(offset), 'off')

        if opkind == 'get':
            # getfield[field_T](ptr, attr, offset)
            assert wop_v is None
            w_func = vm.call(UNSAFE.w_getfield, [w_field_T])
            assert isinstance(w_func, W_Func)
            return W_OpImpl(w_func, [wop_ptr, wop_attr, wop_offset])
        else:
            # setfield[field_T](ptr, attr, offset, v)
            assert wop_v is not None
            w_func = vm.call(UNSAFE.w_setfield, [w_field_T])
            assert isinstance(w_func, W_Func)
            return W_OpImpl(w_func, [wop_ptr, wop_attr, wop_offset, wop_v])

    @no_type_check
    @builtin_func(QN(f'unsafe::ptr_{w_T.name}_load'))
    def w_ptr_load(vm: 'SPyVM', w_ptr: W_MyPtr, w_i: W_I32) -> T:
        base = w_ptr.addr
        length = w_ptr.length
        i = vm.unwrap_i32(w_i)
        addr = base + ITEMSIZE * i
        if i >= length:
            msg = (f"ptr_load out of bounds: 0x{addr:x}[{i}] "
                   f"(upper bound: {length})")
            raise SPyPanicError(msg)
        return vm.call_generic(
            UNSAFE.w_mem_read,
            [w_T],
            [vm.wrap(addr)]
        )

    @no_type_check
    @builtin_func(QN(f'unsafe::ptr_{w_T.name}_store'))
    def w_ptr_store(vm: 'SPyVM', w_ptr: W_MyPtr,
                  w_i: W_I32, w_v: T) -> W_Void:
        base = w_ptr.addr
        length = w_ptr.length
        i = vm.unwrap_i32(w_i)
        addr = base + ITEMSIZE * i
        if i >= length:
            msg = (f"ptr_store out of bounds: 0x{addr:x}[{i}] "
                   f"(upper bound: {length})")
            raise SPyPanicError(msg)
        return vm.call_generic(
            UNSAFE.w_mem_write,
            [w_T],
            [vm.wrap(addr), w_v]
        )

    W_MyPtr.__name__ = W_MyPtr.__qualname__ = interp_name
    return vm.wrap(W_MyPtr)



@UNSAFE.builtin_func(color='blue')
def w_getfield(vm: 'SPyVM', w_T: W_Type) -> W_Dynamic:
    # fields can be returned "by value" or "by reference". Primitive types
    # returned by value, but struct types are always returned by reference
    # (i.e., we return a pointer to it).
    if w_T.is_struct(vm):
        w_T = vm.call(w_make_ptr_type, [w_T])
        by = 'byref'
    else:
        by = 'byval'

    T = w_T.pyclass  # W_I32
    t = w_T.name     # 'i32'
    t = hack_hack_fix_typename(t)

    # unsafe::getfield_prim_i32
    # unsafe::getfield_ref_Point
    @no_type_check
    @builtin_func(QN(f'unsafe::getfield_{by}_{t}'))
    def w_getfield_T(vm: 'SPyVM', w_ptr: W_Ptr, w_attr: W_Str,
                     w_offset: W_I32) -> T:
        """
        NOTE: w_attr is ignored here, but it's used by the C backend
        """
        addr = w_ptr.addr + vm.unwrap_i32(w_offset)
        return vm.call_generic(
            UNSAFE.w_mem_read,
            [w_T],
            [vm.wrap(addr)]
        )
    return w_getfield_T


@UNSAFE.builtin_func(color='blue')
def w_setfield(vm: 'SPyVM', w_T: W_Type) -> W_Dynamic:
    T = w_T.pyclass  # W_I32
    t = w_T.name     # 'i32'

    @no_type_check
    @builtin_func(QN(f'unsafe::setfield_{t}'))  # unsafe::setfield_i32
    def w_setfield_T(vm: 'SPyVM', w_ptr: W_Ptr, w_attr: W_Str,
                     w_offset: W_I32, w_val: T) -> W_Void:
        """
        NOTE: w_attr is ignored here, but it's used by the C backend
        """
        addr = w_ptr.addr + vm.unwrap_i32(w_offset)
        vm.call_generic(
            UNSAFE.w_mem_write,
            [w_T],
            [vm.wrap(addr), w_val]
        )
    return w_setfield_T
