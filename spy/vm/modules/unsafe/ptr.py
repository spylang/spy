from typing import TYPE_CHECKING, ClassVar, Optional, Annotated
import fixedint
from spy.errors import SPyPanicError
from spy.fqn import FQN
from spy.vm.primitive import W_I32, W_Dynamic, W_Void, W_Bool
from spy.vm.object import Member
from spy.vm.b import B
from spy.vm.builtin import builtin_type, builtin_method
from spy.vm.w import W_Object, W_Type, W_Str, W_Func
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.builtin import builtin_func
from . import UNSAFE
from .misc import sizeof
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@UNSAFE.builtin_func(color='blue')
def w_make_ptr_type(vm: 'SPyVM', w_T: W_Type) -> W_Dynamic:
    fqn = FQN('unsafe').join('ptr', [w_T.fqn])  # unsafe::ptr[i32]
    w_ptrtype = W_PtrType(fqn, w_T)
    return w_ptrtype


@UNSAFE.builtin_type('ptrtype')
class W_PtrType(W_Type):
    """
    A specialized ptr type.
    ptr[i32] -> W_PtrType(fqn, B.w_i32)
    """
    w_itemtype: Annotated[W_Type, Member('itemtype')]

    # w_NULL: ???
    # PtrTypes have a NULL member, which you can use like that:
    #    ptr[i32].NULL
    #
    # So ideally, we would like to have a w_NULL Annotated[Member] here, but
    # we cannot because the typing of is a bit problematic.
    #
    # From the point of view of concrete ptr[] types, it's a class variable,
    # roughly equivalent to this:
    #   class ptr[T]:
    #       NULL: ClassVar['Self']
    #
    # HOWEVER, ptr[T] is an instance of PtrType, so NULL is _also_ an instance
    # variable of PtrType. The problem here is that we don't have any good way
    # of declaring its type:
    #   class PtrType:
    #       NULL: ???
    #
    # This happens because giving a PtrType(T) instance, PtrType(T).NULL is of
    # type PtrType(T), and AFAIK there is no syntax to denote that.
    #
    # The workaround is not to use a Member, but to implement .NULL as a
    # special case of op_GETATTR.

    def __init__(self, fqn: FQN, w_itemtype: W_Type) -> None:
        super().__init__(fqn, W_Ptr)
        self.w_itemtype = w_itemtype

    @staticmethod
    @builtin_method('__GETATTR__', color='blue')
    def w_GETATTR(vm: 'SPyVM', wop_ptr: 'W_OpArg',
                  wop_attr: 'W_OpArg') -> 'W_OpImpl':
        attr = wop_attr.blue_unwrap_str(vm)
        if attr == 'NULL':
            # NOTE: the precise spelling of the FQN of NULL matters! The
            # C backend emits a #define to match it, see Context.new_ptr_type
            w_self = wop_ptr.blue_ensure(vm, UNSAFE.w_ptrtype)
            assert isinstance(w_self, W_PtrType)
            w_NULL = W_Ptr(w_self, 0, 0)
            vm.add_global(w_self.fqn.join('NULL'), w_NULL)

            @builtin_func(w_self.fqn, color='blue')  # ptr[i32]::get_NULL
            def w_get_NULL(vm: 'SPyVM') -> Annotated['W_Ptr', w_self]:
                return w_NULL
            return W_OpImpl(w_get_NULL, [])

        else:
            return W_OpImpl.NULL




@UNSAFE.builtin_type('ptr')
class W_BasePtr(W_Object):
    """
    This is the app-level 'ptr' type.

    Since it's a generic type, 'ptr' itself is not supposed to be instantiated.
    Concrete pointers such as 'ptr[i32]' are instances of W_Ptr.
    """

    def __init__(self) -> None:
        raise Exception("You cannot instantiate W_BasePtr, use W_Ptr")

    @staticmethod
    def w_meta_GETITEM(vm: 'SPyVM', wop_p: W_OpArg, wop_T: W_OpArg)-> W_OpImpl:
        return W_OpImpl(w_make_ptr_type, [wop_T])


class W_Ptr(W_BasePtr):
    """
    An actual ptr
    """
    __spy_storage_category__ = 'value'

    # XXX: this works only if we target 32bit platforms such as wasm32, but we
    # need to think of a more general solution
    w_ptrtype: W_PtrType
    addr: fixedint.Int32
    length: fixedint.Int32 # how many items in the array

    def __init__(self, w_ptrtype: W_PtrType,
                 addr: int | fixedint.Int32,
                 length: int | fixedint.Int32) -> None:
        assert type(addr) in (int, fixedint.Int32)
        assert type(length) in (int, fixedint.Int32)
        if addr == 0:
            assert length == 0
        else:
            assert length >= 1
        self.w_ptrtype = w_ptrtype
        self.addr = fixedint.Int32(addr)
        self.length = fixedint.Int32(length)

    def __repr__(self) -> str:
        clsname = self.__class__.__name__
        t = self.w_ptrtype.w_itemtype.fqn.human_name
        if self.addr == 0:
            return f'{clsname}({t}, NULL)'
        else:
            return f'{clsname}({t}, 0x{self.addr:x}, length={self.length})'

    def spy_get_w_type(self, vm: 'SPyVM') -> W_Type:
        return self.w_ptrtype

    def spy_unwrap(self, vm: 'SPyVM') -> 'W_BasePtr':
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

    @builtin_method('__GETITEM__', color='blue')
    @staticmethod
    def w_GETITEM(vm: 'SPyVM', wop_ptr: W_OpArg, wop_i: W_OpArg) -> W_OpImpl:
        w_ptrtype = W_Ptr._get_ptrtype(wop_ptr)
        w_T = w_ptrtype.w_itemtype
        ITEMSIZE = sizeof(w_T)
        PTR = Annotated[W_Ptr, w_ptrtype]
        T = Annotated[W_Object, w_T]

        @builtin_func(w_ptrtype.fqn, 'load')
        def w_ptr_load_T(vm: 'SPyVM', w_ptr: PTR, w_i: W_I32) -> T:
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

    @builtin_method('__SETITEM__', color='blue')
    @staticmethod
    def w_SETITEM(vm: 'SPyVM', wop_ptr: W_OpArg, wop_i: W_OpArg,
                  wop_v: W_OpArg) -> W_OpImpl:
        w_ptrtype = W_Ptr._get_ptrtype(wop_ptr)
        w_T = w_ptrtype.w_itemtype
        ITEMSIZE = sizeof(w_T)
        PTR = Annotated[W_Ptr, w_ptrtype]
        T = Annotated[W_Object, w_T]

        @builtin_func(w_ptrtype.fqn, 'store')
        def w_ptr_store_T(vm: 'SPyVM', w_ptr: PTR, w_i: W_I32, w_v: T)-> None:
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
        PTR = Annotated[W_Ptr, w_ptrtype]

        @builtin_func(w_ptrtype.fqn, 'eq')
        def w_ptr_eq(vm: 'SPyVM', w_ptr1: PTR, w_ptr2: PTR) -> W_Bool:
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
        PTR = Annotated[W_Ptr, w_ptrtype]

        @builtin_func(w_ptrtype.fqn, 'ne')
        def w_ptr_ne(vm: 'SPyVM', w_ptr1: PTR, w_ptr2: PTR) -> W_Bool:
            return vm.wrap(
                w_ptr1.addr != w_ptr2.addr or
                w_ptr1.length != w_ptr1.length
            )  # type: ignore
        return W_OpImpl(w_ptr_ne)

    @staticmethod
    def op_CONVERT_TO(vm: 'SPyVM', w_T: W_Type, wop_x: W_OpArg) -> W_OpImpl:
        if w_T is not B.w_bool:
            return W_OpImpl.NULL
        w_ptrtype = W_Ptr._get_ptrtype(wop_x)
        PTR = Annotated[W_Ptr, w_ptrtype]

        @builtin_func(w_ptrtype.fqn, 'to_bool')
        def w_ptr_to_bool(vm: 'SPyVM', w_ptr: PTR) -> W_Bool:
            if w_ptr.addr == 0:
                return B.w_False
            return B.w_True

        vm.add_global(w_ptr_to_bool.fqn, w_ptr_to_bool)
        return W_OpImpl(w_ptr_to_bool)


    @staticmethod
    def op_GETATTR(vm: 'SPyVM', wop_ptr: W_OpArg,
                   wop_attr: W_OpArg) -> W_OpImpl:
        return W_Ptr._op_ATTR('get', vm, wop_ptr, wop_attr, None)

    @staticmethod
    def op_SETATTR(vm: 'SPyVM', wop_ptr: W_OpArg, wop_attr: W_OpArg,
                   wop_v: W_OpArg) -> W_OpImpl:
        return W_Ptr._op_ATTR('set', vm, wop_ptr, wop_attr, wop_v)

    @staticmethod
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
        wop_offset = W_OpArg.from_w_obj(vm, vm.wrap(offset))

        if opkind == 'get':
            # getfield[field_T](ptr, attr, offset)
            assert wop_v is None
            w_func = vm.fast_call(UNSAFE.w_getfield, [w_field_T])
            assert isinstance(w_func, W_Func)
            return W_OpImpl(w_func, [wop_ptr, wop_attr, wop_offset])
        else:
            # setfield[field_T](ptr, attr, offset, v)
            assert wop_v is not None
            w_func = vm.fast_call(UNSAFE.w_setfield, [w_field_T])
            assert isinstance(w_func, W_Func)
            return W_OpImpl(w_func, [wop_ptr, wop_attr, wop_offset, wop_v])



@UNSAFE.builtin_func(color='blue')
def w_getfield(vm: 'SPyVM', w_T: W_Type) -> W_Dynamic:
    # fields can be returned "by value" or "by reference". Primitive types
    # returned by value, but struct types are always returned by reference
    # (i.e., we return a pointer to it).
    if w_T.is_struct(vm):
        w_T = vm.fast_call(w_make_ptr_type, [w_T])  # type: ignore
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
            assert isinstance(w_T, W_PtrType)
            return W_Ptr(w_T, addr, 1)
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
