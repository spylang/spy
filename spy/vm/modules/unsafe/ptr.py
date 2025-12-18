from typing import TYPE_CHECKING, Annotated, Any, Optional, Self

import fixedint

from spy.errors import WIP, SPyError
from spy.fqn import FQN
from spy.location import Loc
from spy.vm.b import B
from spy.vm.builtin import IRTag, builtin_method, builtin_property
from spy.vm.member import Member
from spy.vm.modules.types import W_Loc
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.primitive import W_I32, W_Bool, W_Dynamic
from spy.vm.struct import W_StructField, W_StructType
from spy.vm.w import W_Func, W_Object, W_Str, W_Type

from . import UNSAFE
from .misc import sizeof

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@UNSAFE.builtin_func(color="blue")
def w_make_ptr_type(vm: "SPyVM", w_T: W_Type) -> W_Dynamic:
    fqn = FQN("unsafe").join("ptr", [w_T.fqn])  # unsafe::ptr[i32]
    w_ptrtype = W_PtrType.from_itemtype(fqn, w_T)
    return w_ptrtype


@UNSAFE.builtin_type("ptrtype")
class W_PtrType(W_Type):
    """
    A specialized ptr type.
    ptr[i32] -> W_PtrType(fqn, B.w_i32)
    """

    w_itemtype: Annotated[W_Type, Member("itemtype")]

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

    def spy_dir(self, vm: "SPyVM") -> set[str]:
        names = super().spy_dir(vm)
        names.update(self.w_itemtype.spy_dir(vm))
        return names

    @builtin_property("NULL", color="blue", kind="metafunc")
    @staticmethod
    def w_GET_NULL(vm: "SPyVM", wam_self: W_MetaArg) -> W_OpSpec:
        # NOTE: the precise spelling of the FQN of NULL matters! The
        # C backend emits a #define to match it, see Context.new_ptr_type
        w_self = wam_self.blue_ensure(vm, UNSAFE.w_ptrtype)
        assert isinstance(w_self, W_PtrType)
        w_NULL = W_Ptr(w_self, 0, 0)
        vm.add_global(w_self.fqn.join("NULL"), w_NULL)

        @vm.register_builtin_func(w_self.fqn, color="blue")  # ptr[i32]::get_NULL
        def w_get_NULL(vm: "SPyVM") -> Annotated["W_Ptr", w_self]:
            return w_NULL

        return W_OpSpec(w_get_NULL, [])


@UNSAFE.builtin_type("MetaBasePtr")
class W_MetaBasePtr(W_Type):
    """
    This exist solely to be able to do ptr[...]
    """

    @builtin_method("__getitem__", color="blue", kind="metafunc")
    @staticmethod
    def w_GETITEM(vm: "SPyVM", wam_p: W_MetaArg, wam_T: W_MetaArg) -> W_OpSpec:
        return W_OpSpec(w_make_ptr_type, [wam_T])


@UNSAFE.builtin_type("ptr", W_MetaClass=W_MetaBasePtr)
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

    __spy_storage_category__ = "value"

    # XXX: this works only if we target 32bit platforms such as wasm32, but we
    # need to think of a more general solution
    w_ptrtype: W_PtrType
    addr: fixedint.Int32
    length: fixedint.Int32  # how many items in the array

    def __init__(
        self,
        w_ptrtype: W_PtrType,
        addr: int | fixedint.Int32,
        length: int | fixedint.Int32,
    ) -> None:
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
            return f"{clsname}({t}, NULL)"
        else:
            return f"{clsname}({t}, 0x{self.addr:x}, length={self.length})"

    def spy_get_w_type(self, vm: "SPyVM") -> W_Type:
        return self.w_ptrtype

    def spy_unwrap(self, vm: "SPyVM") -> "W_BasePtr":
        return self

    def spy_key(self, vm: "SPyVM") -> Any:
        t = self.w_ptrtype.spy_key(vm)
        return ("ptr", t, self.addr, self.length)

    @staticmethod
    def _get_ptrtype(wam_ptr: W_MetaArg) -> W_PtrType:
        w_ptrtype = wam_ptr.w_static_T
        if isinstance(w_ptrtype, W_PtrType):
            return w_ptrtype
        else:
            # I think we can get here if we have something typed 'ptr' as
            # opposed to e.g. 'ptr[i32]'
            assert False, "FIXME: raise a nice error"

    @builtin_method("__getitem__", color="blue", kind="metafunc")
    @staticmethod
    def w_GETITEM(vm: "SPyVM", wam_ptr: W_MetaArg, wam_i: W_MetaArg) -> W_OpSpec:
        w_ptrtype = W_Ptr._get_ptrtype(wam_ptr)
        w_T = w_ptrtype.w_itemtype
        ITEMSIZE = sizeof(w_T)
        PTR = Annotated[W_Ptr, w_ptrtype]

        if w_T.is_struct(vm):
            w_T = vm.fast_call(w_make_ptr_type, [w_T])  # type: ignore
            by = "byref"
        else:
            by = "byval"

        T = Annotated[W_Object, w_T]
        irtag = IRTag("ptr.getitem")

        @vm.register_builtin_func(w_ptrtype.fqn, f"getitem_{by}", irtag=irtag)
        def w_ptr_getitem_T(vm: "SPyVM", w_ptr: PTR, w_i: W_I32, w_loc: W_Loc) -> T:
            base = w_ptr.addr
            length = w_ptr.length
            i = vm.unwrap_i32(w_i)
            addr = base + ITEMSIZE * i
            if not (0 <= i < length):
                msg = (
                    f"ptr_getitem out of bounds: 0x{addr:x}[{i}] "
                    f"(upper bound: {length})"
                )
                raise SPyError.simple("W_PanicError", msg, "", w_loc.loc)

            if by == "byref":
                assert isinstance(w_T, W_PtrType)
                return W_Ptr(w_T, addr, length - i)
            else:
                return vm.call_generic(UNSAFE.w_mem_read, [w_T], [vm.wrap(addr)])

        # for now we explicitly pass a loc to use to construct a
        # W_PanicError. Probably we want a more generic way to do that instead
        # of hardcodid locs everywhere
        wam_loc = W_MetaArg.from_w_obj(vm, W_Loc(wam_ptr.loc))
        return W_OpSpec(w_ptr_getitem_T, [wam_ptr, wam_i, wam_loc])

    @builtin_method("__setitem__", color="blue", kind="metafunc")
    @staticmethod
    def w_SETITEM(
        vm: "SPyVM", wam_ptr: W_MetaArg, wam_i: W_MetaArg, wam_v: W_MetaArg
    ) -> W_OpSpec:
        w_ptrtype = W_Ptr._get_ptrtype(wam_ptr)
        w_T = w_ptrtype.w_itemtype
        ITEMSIZE = sizeof(w_T)
        PTR = Annotated[W_Ptr, w_ptrtype]
        T = Annotated[W_Object, w_T]
        irtag = IRTag("ptr.store")

        @vm.register_builtin_func(w_ptrtype.fqn, "store", irtag=irtag)
        def w_ptr_store_T(
            vm: "SPyVM", w_ptr: PTR, w_i: W_I32, w_v: T, w_loc: W_Loc
        ) -> None:
            base = w_ptr.addr
            length = w_ptr.length
            i = vm.unwrap_i32(w_i)
            addr = base + ITEMSIZE * i
            if not (0 <= i < length):
                msg = (
                    f"ptr_store out of bounds: 0x{addr:x}[{i}] (upper bound: {length})"
                )
                raise SPyError.simple("W_PanicError", msg, "", w_loc.loc)
            vm.call_generic(UNSAFE.w_mem_write, [w_T], [vm.wrap(addr), w_v])

        wam_loc = W_MetaArg.from_w_obj(vm, W_Loc(wam_ptr.loc))
        return W_OpSpec(w_ptr_store_T, [wam_ptr, wam_i, wam_v, wam_loc])

    @builtin_method("__convert_to__", color="blue", kind="metafunc")
    @staticmethod
    def w_CONVERT_TO(
        vm: "SPyVM", wam_expT: W_MetaArg, wam_gotT: W_MetaArg, wam_x: W_MetaArg
    ) -> W_OpSpec:
        w_T = wam_expT.w_blueval
        w_ptrtype = W_Ptr._get_ptrtype(wam_x)
        T = Annotated[W_Object, w_T]
        PTR = Annotated[W_Ptr, w_ptrtype]

        if w_T is B.w_bool:

            @vm.register_builtin_func(w_ptrtype.fqn, "to_bool")
            def w_ptr_to_bool(vm: "SPyVM", w_ptr: PTR) -> W_Bool:
                if w_ptr.addr == 0:
                    return B.w_False
                return B.w_True

            return W_OpSpec(w_ptr_to_bool)

        elif isinstance(w_T, W_StructType) and w_T is w_ptrtype.w_itemtype:
            # we are trying to convert 'ptr[Point]' into 'Point'
            #
            # this is a temporary hack: currently if we have an array of
            # structs, arr[n] ALWAYS retrun a ptr[Struct] (it's always by
            # ref), and thus we don't really have a way to derefeence it.
            #
            # PROBABLY the right solution is to introduce a different type
            # 'ref[Point]', similar to 'Point&' in C++, and then declare that
            # we can convert from 'ref[Point]' to 'Point' but not from
            # 'ptr[Point]' to 'Point'. What a mess.
            irtag = IRTag("ptr.deref")

            @vm.register_builtin_func(w_ptrtype.fqn, "deref", irtag=irtag)
            def w_ptr_deref(vm: "SPyVM", w_ptr: PTR) -> T:
                addr = w_ptr.addr
                return vm.call_generic(UNSAFE.w_mem_read, [w_T], [vm.wrap(addr)])

            return W_OpSpec(w_ptr_deref)

        else:
            return W_OpSpec.NULL

    @builtin_method("__getattribute__", color="blue", kind="metafunc")
    @staticmethod
    def w_GETATTRIBUTE(
        vm: "SPyVM", wam_ptr: W_MetaArg, wam_name: W_MetaArg
    ) -> W_OpSpec:
        return W_Ptr.op_ATTR("get", vm, wam_ptr, wam_name, None)

    @builtin_method("__setattr__", color="blue", kind="metafunc")
    @staticmethod
    def w_SETATTR(
        vm: "SPyVM", wam_ptr: W_MetaArg, wam_name: W_MetaArg, wam_v: W_MetaArg
    ) -> W_OpSpec:
        return W_Ptr.op_ATTR("set", vm, wam_ptr, wam_name, wam_v)

    @staticmethod
    def op_ATTR(
        opkind: str,
        vm: "SPyVM",
        wam_ptr: W_MetaArg,
        wam_name: W_MetaArg,
        wam_v: Optional[W_MetaArg],
    ) -> W_OpSpec:
        """
        Implement both w_GETATTRIBUTE and w_SETATTR.
        """
        w_ptrtype = W_Ptr._get_ptrtype(wam_ptr)
        w_T = w_ptrtype.w_itemtype
        # attributes are supported only on ptr-to-structs
        if not w_T.is_struct(vm):
            return W_OpSpec.NULL

        assert isinstance(w_T, W_StructType)
        name = wam_name.blue_unwrap_str(vm)
        if name not in w_T.dict_w:
            return W_OpSpec.NULL

        w_obj = w_T.dict_w[name]
        if not isinstance(w_obj, W_StructField):
            raise WIP("don't know how to read this attribute from a ptr-to-struct")
        w_field = w_obj

        offset = w_field.offset
        wam_offset = W_MetaArg.from_w_obj(vm, vm.wrap(offset))

        if opkind == "get":
            # ptr_getfield[field_T](ptr, name, offset)
            assert wam_v is None
            w_func = vm.fast_call(UNSAFE.w_ptr_getfield, [w_field.w_T])
            assert isinstance(w_func, W_Func)
            return W_OpSpec(w_func, [wam_ptr, wam_name, wam_offset])
        else:
            # ptr_setfield[field_T](ptr, name, offset, v)
            assert wam_v is not None
            w_func = vm.fast_call(UNSAFE.w_ptr_setfield, [w_field.w_T])
            assert isinstance(w_func, W_Func)
            return W_OpSpec(w_func, [wam_ptr, wam_name, wam_offset, wam_v])


@UNSAFE.builtin_func(color="blue")
def w_ptr_getfield(vm: "SPyVM", w_T: W_Type) -> W_Dynamic:
    # fields can be returned "by value" or "by reference". Primitive types
    # returned by value, but struct types are always returned by reference
    # (i.e., we return a pointer to it).
    if w_T.is_struct(vm):
        w_T = vm.fast_call(w_make_ptr_type, [w_T])  # type: ignore
        by = "byref"
    else:
        by = "byval"

    T = Annotated[W_Object, w_T]

    # e.g.:
    # unsafe::getfield_byval[i32]
    # unsafe::getfield_byref[ptr[Point]]
    tag = IRTag("ptr.getfield", by=by)

    @vm.register_builtin_func("unsafe", f"ptr_getfield_{by}", [w_T.fqn], irtag=tag)
    def w_ptr_getfield_T(
        vm: "SPyVM", w_ptr: W_Ptr, w_name: W_Str, w_offset: W_I32
    ) -> T:
        """
        NOTE: w_name is ignored here, but it's used by the C backend
        """
        addr = w_ptr.addr + vm.unwrap_i32(w_offset)
        if by == "byref":
            assert isinstance(w_T, W_PtrType)
            return W_Ptr(w_T, addr, 1)
        else:
            return vm.call_generic(UNSAFE.w_mem_read, [w_T], [vm.wrap(addr)])

    return w_ptr_getfield_T


@UNSAFE.builtin_func(color="blue")
def w_ptr_setfield(vm: "SPyVM", w_T: W_Type) -> W_Dynamic:
    T = Annotated[W_Object, w_T]

    # fqn is something like unsafe::setfield[i32]
    irtag = IRTag("ptr.setfield")

    @vm.register_builtin_func("unsafe", "ptr_setfield", [w_T.fqn], irtag=irtag)
    def w_ptr_setfield_T(
        vm: "SPyVM", w_ptr: W_Ptr, w_name: W_Str, w_offset: W_I32, w_val: T
    ) -> None:
        """
        NOTE: w_name is ignored here, but it's used by the C backend
        """
        addr = w_ptr.addr + vm.unwrap_i32(w_offset)
        vm.call_generic(UNSAFE.w_mem_write, [w_T], [vm.wrap(addr), w_val])

    return w_ptr_setfield_T
