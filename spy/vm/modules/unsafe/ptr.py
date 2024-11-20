from typing import TYPE_CHECKING, ClassVar, Optional, Annotated
import fixedint
from spy.errors import SPyPanicError
from spy.fqn import FQN
from spy.vm.primitive import W_I32, W_Dynamic, W_Void, W_Bool
from spy.vm.b import B
from spy.vm.builtin import builtin_type
from spy.vm.w import W_Object, W_Type, W_Str, W_Func
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.builtin import builtin_func
from . import UNSAFE
from .misc import sizeof
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

def is_ptr_type(w_T: W_Type) -> bool:
    return issubclass(w_T.pyclass, W_Ptr)


class W_PtrType(W_Type):
    w_itemtype: W_Type

    def __init__(self, fqn: FQN, pyclass, w_itemtype: W_Type) -> None:
        super().__init__(fqn, pyclass)
        self.w_itemtype = w_itemtype


@UNSAFE.builtin_type('ptr')
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

    def spy_unwrap(self, vm: 'SPyVM') -> 'W_Ptr':
        return self

    @staticmethod
    def _get_ptrtype(wop_ptr: W_OpArg) -> W_PtrType:
        w_ptrtype = wop_ptr.w_static_type
        if isinstance(w_ptrtype, W_PtrType):
            return w_ptrtype
        else:
            # I think we can get here if we have something typed 'ptr' as
            # opposed to e.g. 'ptr[i32]'
            assert False, 'FIXME: raise a nice error'

    @staticmethod
    def op_GETITEM(vm: 'SPyVM', wop_ptr: W_OpArg, wop_i: W_OpArg) -> W_OpImpl:
        w_ptrtype = W_Ptr._get_ptrtype(wop_ptr)
        w_T = w_ptrtype.w_itemtype
        ITEMSIZE = sizeof(w_T)
        T = Annotated[W_Object, w_T]

        @builtin_func(w_ptrtype.fqn, 'load')
        def w_ptr_load_T(vm: 'SPyVM', w_ptr: W_Ptr, w_i: W_I32) -> T:
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
        return W_OpImpl(w_ptr_load_T)

    @staticmethod
    def op_SETITEM(vm: 'SPyVM', wop_ptr: W_OpArg, wop_i: W_OpArg,
                   wop_v: W_OpArg) -> W_OpImpl:
        w_ptrtype = W_Ptr._get_ptrtype(wop_ptr)
        w_T = w_ptrtype.w_itemtype
        ITEMSIZE = sizeof(w_T)
        T = Annotated[W_Object, w_T]

        @builtin_func(w_ptrtype.fqn, 'store')
        def w_ptr_store_T(vm: 'SPyVM', w_ptr: W_Ptr, w_i: W_I32, w_v: T)-> None:
            base = w_ptr.addr
            length = w_ptr.length
            i = vm.unwrap_i32(w_i)
            addr = base + ITEMSIZE * i
            if i >= length:
                msg = (f"ptr_store out of bounds: 0x{addr:x}[{i}] "
                       f"(upper bound: {length})")
                raise SPyPanicError(msg)
            vm.call_generic(
                UNSAFE.w_mem_write,
                [w_T],
                [vm.wrap(addr), w_v]
            )
        return W_OpImpl(w_ptr_store_T)

    @staticmethod
    def op_EQ(vm: 'SPyVM', wop_l: W_OpArg, wop_r: W_OpArg) -> W_OpImpl:
        w_ltype = wop_l.w_static_type
        w_rtype = wop_r.w_static_type
        if w_ltype is not w_rtype:
            return W_OpImpl.NULL
        w_ptrtype = W_Ptr._get_ptrtype(wop_l)

        @builtin_func(w_ptrtype.fqn, 'eq')
        def w_ptr_eq(vm: 'SPyVM', w_ptr1: W_Ptr, w_ptr2: W_Ptr) -> W_Bool:
            return vm.wrap(
                w_ptr1.addr == w_ptr2.addr and
                w_ptr1.length == w_ptr1.length
            )  # type: ignore
        return W_OpImpl(w_ptr_eq)

    @staticmethod
    def op_NE(vm: 'SPyVM', wop_l: W_OpArg, wop_r: W_OpArg) -> W_OpImpl:
        w_ltype = wop_l.w_static_type
        w_rtype = wop_r.w_static_type
        if w_ltype is not w_rtype:
            return W_OpImpl.NULL
        w_ptrtype = W_Ptr._get_ptrtype(wop_l)

        @builtin_func(w_ptrtype.fqn, 'ne')
        def w_ptr_ne(vm: 'SPyVM', w_ptr1: W_Ptr, w_ptr2: W_Ptr) -> W_Bool:
            return vm.wrap(
                w_ptr1.addr != w_ptr2.addr or
                w_ptr1.length != w_ptr1.length
            )  # type: ignore
        return W_OpImpl(w_ptr_ne)

    @staticmethod
    def op_GETATTR(vm: 'SPyVM', wop_ptr: W_OpArg,
                   wop_attr: W_OpArg) -> W_OpImpl:
        return W_Ptr._op_ATTR('get', vm, wop_ptr, wop_attr, None)

    @staticmethod
    def op_SETATTR(vm: 'SPyVM', wop_ptr: W_OpArg, wop_attr: W_OpArg,
                   wop_v: W_OpArg) -> W_OpImpl:
        return W_Ptr._op_ATTR('set', vm, wop_ptr, wop_attr, wop_v)

    def _op_ATTR(opkind: str, vm: 'SPyVM', wop_ptr: W_OpArg, wop_attr: W_OpArg,
                 wop_v: Optional[W_OpArg]) -> W_OpImpl:
        """
        Implement both op_GETATTR and op_SETATTR.
        """
        from .struct import W_StructType
        w_ptrtype = W_Ptr._get_ptrtype(wop_ptr)
        w_T = w_ptrtype.w_itemtype
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



@UNSAFE.builtin_func(color='blue')
def w_make_ptr_type(vm: 'SPyVM', w_T: W_Type) -> W_Dynamic:

    class W_MyPtr(W_Ptr):
        __qualname__ = f'W_Ptr[{T.__name__}]' # e.g. W_Ptr[W_I32]

    W_MyPtr.__name__ = W_MyPtr.__qualname__

    fqn = FQN('unsafe').join('ptr', [w_T.fqn])  # unsafe::ptr[i32]
    w_ptrtype = W_PtrType(fqn, W_MyPtr, w_T)
    W_MyPtr._w = w_ptrtype # poor's man @builtin_type

    return w_ptrtype



@UNSAFE.builtin_func(color='blue')
def w_getfield(vm: 'SPyVM', w_T: W_Type) -> W_Dynamic:
    # fields can be returned "by value" or "by reference". Primitive types
    # returned by value, but struct types are always returned by reference
    # (i.e., we return a pointer to it).
    if w_T.is_struct(vm):
        w_T = vm.call(w_make_ptr_type, [w_T])  # type: ignore
        by = 'byref'
    else:
        by = 'byval'

    T = Annotated[W_Object, w_T]

    # e.g.:
    # unsafe::getfield_byval[i32]
    # unsafe::getfield_byref[ptr[Point]]
    @builtin_func('unsafe', f'getfield_{by}', [w_T.fqn])
    def w_getfield_T(vm: 'SPyVM', w_ptr: W_Ptr, w_attr: W_Str,
                     w_offset: W_I32) -> T:
        """
        NOTE: w_attr is ignored here, but it's used by the C backend
        """
        addr = w_ptr.addr + vm.unwrap_i32(w_offset)
        if by == 'byref':
            assert issubclass(w_T.pyclass, W_Ptr)
            return w_T.pyclass(addr, 1)
        else:
            return vm.call_generic(
                UNSAFE.w_mem_read,
                [w_T],
                [vm.wrap(addr)]
            )
    return w_getfield_T


@UNSAFE.builtin_func(color='blue')
def w_setfield(vm: 'SPyVM', w_T: W_Type) -> W_Dynamic:
    T = Annotated[W_Object, w_T]

    @builtin_func('unsafe', 'setfield', [w_T.fqn])  # unsafe::setfield[i32]
    def w_setfield_T(vm: 'SPyVM', w_ptr: W_Ptr, w_attr: W_Str,
                     w_offset: W_I32, w_val: T) -> None:
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
