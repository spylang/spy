from typing import TYPE_CHECKING, Optional, Annotated, Self, Any
import fixedint
from spy.location import Loc
from spy.errors import SPyError
from spy.fqn import FQN
from spy.vm.primitive import W_I32, W_Dynamic, W_Bool
from spy.vm.member import Member
from spy.vm.b import B
from spy.vm.builtin import builtin_method, builtin_property
from spy.vm.w import W_Object, W_Type, W_Str, W_Func
from spy.vm.modules.types import W_Loc
from spy.vm.opspec import W_OpSpec, W_MetaArg
from . import UNSAFE
from .misc import sizeof
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@UNSAFE.builtin_func(color='blue')
def w_make_ptr_type(vm: 'SPyVM', w_T: W_Type) -> W_Dynamic:
    fqn = FQN('unsafe').join('ptr', [w_T.fqn])  # unsafe::ptr[i32]
    w_ptrtype = W_PtrType.from_itemtype(fqn, w_T)
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
    # property.

    @classmethod
    def from_itemtype(cls, fqn: FQN, w_itemtype: W_Type) -> Self:
        w_T = cls.from_pyclass(fqn, W_Ptr)
        w_T.w_itemtype = w_itemtype
        return w_T

    @builtin_property('NULL', color='blue', kind='metafunc')
    @staticmethod
    def w_GET_NULL(vm: 'SPyVM', wm_self: W_MetaArg) -> W_OpSpec:
        # NOTE: the precise spelling of the FQN of NULL matters! The
        # C backend emits a #define to match it, see Context.new_ptr_type
        w_self = wm_self.blue_ensure(vm, UNSAFE.w_ptrtype)
        assert isinstance(w_self, W_PtrType)
        w_NULL = W_Ptr(w_self, 0, 0)
        vm.add_global(w_self.fqn.join('NULL'), w_NULL)

        @vm.register_builtin_func(w_self.fqn, color='blue')  # ptr[i32]::get_NULL
        def w_get_NULL(vm: 'SPyVM') -> Annotated['W_Ptr', w_self]:
            return w_NULL
        return W_OpSpec(w_get_NULL, [])


@UNSAFE.builtin_type('MetaBasePtr')
class W_MetaBasePtr(W_Type):
    """
    This exist solely to be able to do ptr[...]
    """

    @builtin_method('__getitem__', color='blue', kind='metafunc')
    @staticmethod
    def w_GETITEM(vm: 'SPyVM', wm_p: W_MetaArg, wm_T: W_MetaArg)-> W_OpSpec:
        return W_OpSpec(w_make_ptr_type, [wm_T])


@UNSAFE.builtin_type('ptr', W_MetaClass=W_MetaBasePtr)
class W_BasePtr(W_Object):
    """
    This is the app-level 'ptr' type.

    Since it's a generic type, 'ptr' itself is not supposed to be instantiated.
    Concrete pointers such as 'ptr[i32]' are instances of W_Ptr.
    """

    def __init__(self) -> None:
        raise Exception("You cannot instantiate W_BasePtr, use W_Ptr")

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

    def spy_key(self, vm: 'SPyVM') -> Any:
        t = self.w_ptrtype.spy_key(vm)
        return ('ptr', t, self.addr, self.length)

    @staticmethod
    def _get_ptrtype(wm_ptr: W_MetaArg) -> W_PtrType:
        w_ptrtype = wm_ptr.w_static_T
        if isinstance(w_ptrtype, W_PtrType):
            return w_ptrtype
        else:
            # I think we can get here if we have something typed 'ptr' as
            # opposed to e.g. 'ptr[i32]'
            assert False, 'FIXME: raise a nice error'

    @builtin_method('__getitem__', color='blue', kind='metafunc')
    @staticmethod
    def w_GETITEM(vm: 'SPyVM', wm_ptr: W_MetaArg, wm_i: W_MetaArg) -> W_OpSpec:
        w_ptrtype = W_Ptr._get_ptrtype(wm_ptr)
        w_T = w_ptrtype.w_itemtype
        ITEMSIZE = sizeof(w_T)
        PTR = Annotated[W_Ptr, w_ptrtype]

        if w_T.is_struct(vm):
            w_T = vm.fast_call(w_make_ptr_type, [w_T])  # type: ignore
            by = 'byref'
        else:
            by = 'byval'

        T = Annotated[W_Object, w_T]

        @vm.register_builtin_func(w_ptrtype.fqn, f'getitem_{by}')
        def w_ptr_getitem_T(
            vm: 'SPyVM',
            w_ptr: PTR,
            w_i: W_I32,
            w_loc: W_Loc
        ) -> T:
            base = w_ptr.addr
            length = w_ptr.length
            i = vm.unwrap_i32(w_i)
            addr = base + ITEMSIZE * i
            if i >= length:
                msg = (f"ptr_getitem out of bounds: 0x{addr:x}[{i}] "
                       f"(upper bound: {length})")
                raise SPyError.simple("W_PanicError", msg, "", w_loc.loc)

            if by == 'byref':
                assert isinstance(w_T, W_PtrType)
                return W_Ptr(w_T, addr, length-i)
            else:
                return vm.call_generic(
                    UNSAFE.w_mem_read,
                    [w_T],
                    [vm.wrap(addr)]
                )

        # for now we explicitly pass a loc to use to construct a
        # W_PanicError. Probably we want a more generic way to do that instead
        # of hardcodid locs everywhere
        wm_loc = W_MetaArg.from_w_obj(vm, W_Loc(wm_ptr.loc))
        return W_OpSpec(w_ptr_getitem_T, [wm_ptr, wm_i, wm_loc])

    @builtin_method('__setitem__', color='blue', kind='metafunc')
    @staticmethod
    def w_SETITEM(vm: 'SPyVM', wm_ptr: W_MetaArg, wm_i: W_MetaArg,
                  wm_v: W_MetaArg) -> W_OpSpec:
        w_ptrtype = W_Ptr._get_ptrtype(wm_ptr)
        w_T = w_ptrtype.w_itemtype
        ITEMSIZE = sizeof(w_T)
        PTR = Annotated[W_Ptr, w_ptrtype]
        T = Annotated[W_Object, w_T]

        @vm.register_builtin_func(w_ptrtype.fqn, 'store')
        def w_ptr_store_T(
            vm: 'SPyVM',
            w_ptr: PTR,
            w_i: W_I32,
            w_v: T,
            w_loc: W_Loc
        )-> None:
            base = w_ptr.addr
            length = w_ptr.length
            i = vm.unwrap_i32(w_i)
            addr = base + ITEMSIZE * i
            if i >= length:
                msg = (f"ptr_store out of bounds: 0x{addr:x}[{i}] "
                       f"(upper bound: {length})")
                raise SPyError.simple("W_PanicError", msg, "", w_loc.loc)
            vm.call_generic(
                UNSAFE.w_mem_write,
                [w_T],
                [vm.wrap(addr), w_v]
            )

        wm_loc = W_MetaArg.from_w_obj(vm, W_Loc(wm_ptr.loc))
        return W_OpSpec(w_ptr_store_T, [wm_ptr, wm_i, wm_v, wm_loc])

    @builtin_method('__convert_to__', color='blue', kind='metafunc')
    @staticmethod
    def w_CONVERT_TO(vm: 'SPyVM', wm_T: W_MetaArg, wm_x: W_MetaArg) -> W_OpSpec:
        w_T = wm_T.w_blueval
        w_ptrtype = W_Ptr._get_ptrtype(wm_x)
        PTR = Annotated[W_Ptr, w_ptrtype]

        if w_T is B.w_bool:
            @vm.register_builtin_func(w_ptrtype.fqn, 'to_bool')
            def w_ptr_to_bool(vm: 'SPyVM', w_ptr: PTR) -> W_Bool:
                if w_ptr.addr == 0:
                    return B.w_False
                return B.w_True
            return W_OpSpec(w_ptr_to_bool)

        else:
            return W_OpSpec.NULL

    @builtin_method('__getattribute__', color='blue', kind='metafunc')
    @staticmethod
    def w_GETATTRIBUTE(vm: 'SPyVM', wm_ptr: W_MetaArg,
                       wm_name: W_MetaArg) -> W_OpSpec:
        return W_Ptr.op_ATTR('get', vm, wm_ptr, wm_name, None)

    @builtin_method('__setattr__', color='blue', kind='metafunc')
    @staticmethod
    def w_SETATTR(vm: 'SPyVM', wm_ptr: W_MetaArg, wm_name: W_MetaArg,
                  wm_v: W_MetaArg) -> W_OpSpec:
        return W_Ptr.op_ATTR('set', vm, wm_ptr, wm_name, wm_v)

    @staticmethod
    def op_ATTR(opkind: str, vm: 'SPyVM', wm_ptr: W_MetaArg, wm_name: W_MetaArg,
                wm_v: Optional[W_MetaArg]) -> W_OpSpec:
        """
        Implement both w_GETATTRIBUTE and w_SETATTR.
        """
        from .struct import W_StructType
        w_ptrtype = W_Ptr._get_ptrtype(wm_ptr)
        w_T = w_ptrtype.w_itemtype
        # attributes are supported only on ptr-to-structs
        if not w_T.is_struct(vm):
            return W_OpSpec.NULL

        assert isinstance(w_T, W_StructType)
        name = wm_name.blue_unwrap_str(vm)
        if name not in w_T.fields:
            return W_OpSpec.NULL

        w_field_T = w_T.fields[name]
        offset = w_T.offsets[name]
        wm_offset = W_MetaArg.from_w_obj(vm, vm.wrap(offset))

        if opkind == 'get':
            # getfield[field_T](ptr, name, offset)
            assert wm_v is None
            w_func = vm.fast_call(UNSAFE.w_getfield, [w_field_T])
            assert isinstance(w_func, W_Func)
            return W_OpSpec(w_func, [wm_ptr, wm_name, wm_offset])
        else:
            # setfield[field_T](ptr, name, offset, v)
            assert wm_v is not None
            w_func = vm.fast_call(UNSAFE.w_setfield, [w_field_T])
            assert isinstance(w_func, W_Func)
            return W_OpSpec(w_func, [wm_ptr, wm_name, wm_offset, wm_v])



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
    @vm.register_builtin_func('unsafe', f'getfield_{by}', [w_T.fqn])
    def w_getfield_T(vm: 'SPyVM', w_ptr: W_Ptr, w_name: W_Str,
                     w_offset: W_I32) -> T:
        """
        NOTE: w_name is ignored here, but it's used by the C backend
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

    @vm.register_builtin_func('unsafe', 'setfield', [w_T.fqn])  # unsafe::setfield[i32]
    def w_setfield_T(vm: 'SPyVM', w_ptr: W_Ptr, w_name: W_Str,
                     w_offset: W_I32, w_val: T) -> None:
        """
        NOTE: w_name is ignored here, but it's used by the C backend
        """
        addr = w_ptr.addr + vm.unwrap_i32(w_offset)
        vm.call_generic(
            UNSAFE.w_mem_write,
            [w_T],
            [vm.wrap(addr), w_val]
        )
    return w_setfield_T
