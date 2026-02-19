"""
Hierarchy of "pointer types" in SPy:

W_MemLocType
├── W_PtrType
    ├── W_PtrType("raw", ...)
    └── W_PtrType("gc", ...)
└── W_RefType
    ├── W_RefType("raw", ...)
    └── W_RefType("gc", ...)


At low level, all these types are basically the same thing and ultimately points to a
typed location in memory.

The biggest difference between ptrs and refs is what app-level operations are available
on each:

  - ptr[T] can be treated as an array and indexed with []; p[n] returns a ref[T];

  - ref[T] can be implicitly converted to T

  - both supports getattr and setattr to interact with attributes of the struct they
    point to
"""

from typing import TYPE_CHECKING, Annotated, Any, Literal, Optional, Self

import fixedint

from spy.errors import WIP, SPyError
from spy.fqn import FQN
from spy.location import Loc
from spy.vm.b import B
from spy.vm.builtin import IRTag, builtin_method, builtin_property
from spy.vm.function import W_ASTFunc
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


MEMKIND = Literal["raw", "gc"]


@UNSAFE.builtin_func(color="blue", kind="generic")
def w_raw_ptr(vm: "SPyVM", w_T: W_Type) -> W_Dynamic:
    """
    The raw_ptr[T] generic type
    """
    fqn = FQN("unsafe").join("raw_ptr", [w_T.fqn])  # unsafe::raw_ptr[i32]
    w_ptrtype = W_PtrType.from_itemtype(fqn, "raw", w_T)
    return w_ptrtype


@UNSAFE.builtin_func(color="blue", kind="generic")
def w_gc_ptr(vm: "SPyVM", w_T: W_Type) -> W_Dynamic:
    """
    The gc_ptr[T] generic type
    """
    fqn = FQN("unsafe").join("gc_ptr", [w_T.fqn])  # unsafe::gc_ptr[i32]
    w_ptrtype = W_PtrType.from_itemtype(fqn, "gc", w_T)
    return w_ptrtype


@UNSAFE.builtin_func(color="blue", kind="generic")
def w_raw_ref(vm: "SPyVM", w_T: W_Type) -> W_Dynamic:
    """
    The raw_ref[T] generic type
    """
    # the C backend assumes that for every raw_ref[T], the corresponding raw_ptr[T]
    # exists. Let's make sure it does:
    # 1. create raw_ptr[T]
    w_ptrtype = vm.fast_call(w_raw_ptr, [w_T])
    vm.make_fqn_const(w_ptrtype)
    # 2. create raw_ref[T]
    fqn = FQN("unsafe").join("raw_ref", [w_T.fqn])  # unsafe::raw_ref[i32]
    w_reftype = W_RefType.from_itemtype(fqn, "raw", w_T)
    return w_reftype


@UNSAFE.builtin_func(color="blue", kind="generic")
def w_gc_ref(vm: "SPyVM", w_T: W_Type) -> W_Dynamic:
    """
    The gc_ref[T] generic type
    """
    # the C backend assumes that for every gc_ref[T], the corresponding gc_ptr[T]
    # exists. Let's make sure it does:
    # 1. create gc_ptr[T]
    w_ptrtype = vm.fast_call(w_gc_ptr, [w_T])
    vm.make_fqn_const(w_ptrtype)
    # 2. create gc_ref[T]
    fqn = FQN("unsafe").join("gc_ref", [w_T.fqn])  # unsafe::gc_ref[i32]
    w_reftype = W_RefType.from_itemtype(fqn, "gc", w_T)
    return w_reftype


@UNSAFE.builtin_type("_memloctype")
class W_MemLocType(W_Type):
    """
    The base type for all ptrs and refs
    """

    memkind: MEMKIND
    w_itemT: Annotated[W_Type, Member("itemtype")]

    def spy_dir(self, vm: "SPyVM") -> set[str]:
        names = super().spy_dir(vm)
        names.update(self.w_itemT.spy_dir(vm))
        return names


@UNSAFE.builtin_type("rawptrtype")
class W_PtrType(W_MemLocType):
    """
    A specialized ptr type.
    raw_ptr[i32] -> W_PtrType(fqn, "raw", B.w_i32)
    """

    @classmethod
    def from_itemtype(cls, fqn: FQN, memkind: MEMKIND, w_itemT: W_Type) -> Self:
        w_T = cls.from_pyclass(fqn, W_Ptr)
        w_T.memkind = memkind
        w_T.w_itemT = w_itemT
        return w_T

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

    @builtin_property("NULL", color="blue", kind="metafunc")
    @staticmethod
    def w_GET_NULL(vm: "SPyVM", wam_self: W_MetaArg) -> W_OpSpec:
        # NOTE: the precise spelling of the FQN of NULL matters! The
        # C backend emits a #define to match it, see Context.new_ptr_type
        w_self = wam_self.blue_ensure(vm, UNSAFE.w__memloctype)
        assert isinstance(w_self, W_MemLocType)
        w_NULL = W_Ptr(w_self, 0, 0)
        vm.add_global(w_self.fqn.join("NULL"), w_NULL)

        @vm.register_builtin_func(w_self.fqn, color="blue")  # raw_ptr[i32]::get_NULL
        def w_get_NULL(vm: "SPyVM") -> Annotated["W_Ptr", w_self]:
            return w_NULL

        return W_OpSpec(w_get_NULL, [])


@UNSAFE.builtin_type("rawreftype")
class W_RefType(W_MemLocType):
    """
    A specialized ref type.
    raw_ref[i32] -> W_RefType(fqn, "raw", B.w_i32)
    gc_ref[i32] -> W_RefType(fqn, "gc", B.w_i32)
    """

    @classmethod
    def from_itemtype(cls, fqn: FQN, memkind: MEMKIND, w_itemT: W_Type) -> Self:
        w_T = cls.from_pyclass(fqn, W_Ref)
        w_T.memkind = memkind
        w_T.w_itemT = w_itemT
        return w_T

    def as_ptrtype(self, vm: "SPyVM") -> W_PtrType:
        if self.memkind == "raw":
            w_ptr_func = w_raw_ptr
        else:
            w_ptr_func = w_gc_ptr
        w_ptrtype = vm.fast_call(w_ptr_func, [self.w_itemT])
        assert isinstance(w_ptrtype, W_PtrType)
        return w_ptrtype


@UNSAFE.builtin_type("_memloc")
class W_MemLoc(W_Object):
    """
    Base class for raw_ptr, raw_ref, gc_ptr, gc_ref
    """

    w_T: W_MemLocType
    # XXX: this works only if we target 32bit platforms such as wasm32, but we
    # need to think of a more general solution
    addr: fixedint.Int32
    length: fixedint.Int32  # how many items in the array

    def __init__(
        self,
        w_T: W_MemLocType,
        addr: int | fixedint.Int32,
        length: int | fixedint.Int32,
    ) -> None:
        assert type(addr) in (int, fixedint.Int32)
        assert type(length) in (int, fixedint.Int32)
        if addr == 0:
            assert length == 0
        else:
            assert length >= 1
        self.w_T = w_T
        self.addr = fixedint.Int32(addr)
        self.length = fixedint.Int32(length)

    def spy_get_w_type(self, vm: "SPyVM") -> W_Type:
        return self.w_T

    def spy_unwrap(self, vm: "SPyVM") -> "W_MemLoc":
        return self

    @staticmethod
    def _get_memlocT(wam_self: W_MetaArg) -> W_MemLocType:
        w_memlocT = wam_self.w_static_T
        if isinstance(w_memlocT, W_MemLocType):
            return w_memlocT
        else:
            # I think we can get here if we have something typed 'ptr' as
            # opposed to e.g. 'ptr[i32]'
            assert False, "FIXME: raise a nice error"

    @builtin_method("__getattribute__", color="blue", kind="metafunc")
    @staticmethod
    def w_GETATTRIBUTE(
        vm: "SPyVM", wam_self: W_MetaArg, wam_name: W_MetaArg
    ) -> W_OpSpec:
        return W_MemLoc.op_ATTR("get", vm, wam_self, wam_name, None)

    @builtin_method("__setattr__", color="blue", kind="metafunc")
    @staticmethod
    def w_SETATTR(
        vm: "SPyVM", wam_self: W_MetaArg, wam_name: W_MetaArg, wam_v: W_MetaArg
    ) -> W_OpSpec:
        return W_MemLoc.op_ATTR("set", vm, wam_self, wam_name, wam_v)

    @staticmethod
    def op_ATTR(
        opkind: str,
        vm: "SPyVM",
        wam_self: W_MetaArg,
        wam_name: W_MetaArg,
        wam_v: Optional[W_MetaArg],
    ) -> W_OpSpec:
        """
        Implement both w_GETATTRIBUTE and w_SETATTR.
        """
        w_T = W_MemLoc._get_memlocT(wam_self)
        w_itemT = w_T.w_itemT
        # attributes are supported only on ptr-to-structs
        if not w_itemT.is_struct(vm):
            return W_OpSpec.NULL

        assert isinstance(w_itemT, W_StructType)
        name = wam_name.blue_unwrap_str(vm)
        if name not in w_itemT.dict_w:
            return W_OpSpec.NULL

        w_obj = w_itemT.dict_w[name]
        if not isinstance(w_obj, W_StructField):
            raise WIP("don't know how to read this attribute from a ptr-to-struct")
        w_field = w_obj

        offset = w_field.offset
        wam_offset = W_MetaArg.from_w_obj(vm, vm.wrap(offset))

        if opkind == "get":
            # ptr_getfield[field_T, memkind](ptr, name, offset)
            assert wam_v is None
            w_memkind = vm.wrap(w_T.memkind)
            w_func = vm.fast_call(UNSAFE.w_ptr_getfield, [w_field.w_T, w_memkind])
            assert isinstance(w_func, W_Func)
            return W_OpSpec(w_func, [wam_self, wam_name, wam_offset])
        else:
            # ptr_setfield[field_T](ptr, name, offset, v)
            assert wam_v is not None
            w_func = vm.fast_call(UNSAFE.w_ptr_setfield, [w_field.w_T])
            assert isinstance(w_func, W_Func)
            return W_OpSpec(w_func, [wam_self, wam_name, wam_offset, wam_v])


class W_Ptr(W_MemLoc):
    """
    An actual ptr
    """

    __spy_storage_category__ = "value"

    def __repr__(self) -> str:
        clsname = self.__class__.__name__
        t = self.w_T.w_itemT.fqn.human_name
        k = self.w_T.memkind
        if self.addr == 0:
            return f"{clsname}({k!r}, {t}, NULL)"
        else:
            return f"{clsname}({k!r}, {t}, 0x{self.addr:x}, length={self.length})"

    def spy_key(self, vm: "SPyVM") -> Any:
        t = self.w_T.spy_key(vm)
        return ("ptr", t, self.addr, self.length)

    @builtin_method("__getitem__", color="blue", kind="metafunc")
    @staticmethod
    def w_GETITEM(vm: "SPyVM", wam_self: W_MetaArg, wam_i: W_MetaArg) -> W_OpSpec:
        w_T = W_Ptr._get_memlocT(wam_self)
        w_itemT = w_T.w_itemT
        ITEMSIZE = sizeof(w_itemT)
        PTR = Annotated[W_Ptr, w_T]

        if w_itemT.is_struct(vm):
            w_ref_func = w_raw_ref if w_T.memkind == "raw" else w_gc_ref
            w_itemT = vm.fast_call(w_ref_func, [w_itemT])  # type: ignore
            by = "byref"
        else:
            by = "byval"

        ITEM = Annotated[W_Object, w_itemT]
        irtag = IRTag("ptr.getitem")

        @vm.register_builtin_func(w_T.fqn, f"getitem_{by}", irtag=irtag)
        def w_ptr_getitem(vm: "SPyVM", w_ptr: PTR, w_i: W_I32, w_loc: W_Loc) -> ITEM:
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
                assert isinstance(w_itemT, W_RefType)
                return W_Ref(w_itemT, addr, length - i)
            else:
                return vm.call_generic(UNSAFE.w_mem_read, [w_itemT], [vm.wrap(addr)])

        # for now we explicitly pass a loc to use to construct a
        # W_PanicError. Probably we want a more generic way to do that instead
        # of hardcodid locs everywhere
        wam_loc = W_MetaArg.from_w_obj(vm, W_Loc(wam_self.loc))
        return W_OpSpec(w_ptr_getitem, [wam_self, wam_i, wam_loc])

    @builtin_method("__setitem__", color="blue", kind="metafunc")
    @staticmethod
    def w_SETITEM(
        vm: "SPyVM", wam_self: W_MetaArg, wam_i: W_MetaArg, wam_v: W_MetaArg
    ) -> W_OpSpec:
        w_T = W_Ptr._get_memlocT(wam_self)
        w_itemT = w_T.w_itemT
        ITEMSIZE = sizeof(w_itemT)
        PTR = Annotated[W_Ptr, w_T]
        ITEM = Annotated[W_Object, w_itemT]
        irtag = IRTag("ptr.store")

        @vm.register_builtin_func(w_T.fqn, "store", irtag=irtag)
        def w_ptr_store_T(
            vm: "SPyVM", w_ptr: PTR, w_i: W_I32, w_v: ITEM, w_loc: W_Loc
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
            vm.call_generic(UNSAFE.w_mem_write, [w_itemT], [vm.wrap(addr), w_v])

        wam_loc = W_MetaArg.from_w_obj(vm, W_Loc(wam_self.loc))
        return W_OpSpec(w_ptr_store_T, [wam_self, wam_i, wam_v, wam_loc])

    @builtin_method("__convert_to__", color="blue", kind="metafunc")
    @staticmethod
    def w_CONVERT_TO(
        vm: "SPyVM", wam_expT: W_MetaArg, wam_gotT: W_MetaArg, wam_x: W_MetaArg
    ) -> W_OpSpec:
        w_T = wam_expT.w_blueval
        w_ptrtype = W_Ptr._get_memlocT(wam_x)
        PTR = Annotated[W_Ptr, w_ptrtype]

        if w_T is B.w_bool:

            @vm.register_builtin_func(w_ptrtype.fqn, "to_bool")
            def w_ptr_to_bool(vm: "SPyVM", w_ptr: PTR) -> W_Bool:
                if w_ptr.addr == 0:
                    return B.w_False
                return B.w_True

            return W_OpSpec(w_ptr_to_bool)

        else:
            return W_OpSpec.NULL


class W_Ref(W_MemLoc):
    __spy_storage_category__ = "value"

    def spy_key(self, vm: "SPyVM") -> Any:
        t = self.w_T.spy_key(vm)
        return ("ref", t, self.addr, self.length)

    @builtin_method("__convert_to__", color="blue", kind="metafunc")
    @staticmethod
    def w_CONVERT_TO(
        vm: "SPyVM", wam_expT: W_MetaArg, wam_gotT: W_MetaArg, wam_x: W_MetaArg
    ) -> W_OpSpec:
        w_T = wam_expT.w_blueval
        w_reftype = W_Ref._get_memlocT(wam_x)
        assert isinstance(w_reftype, W_RefType)
        T = Annotated[W_Object, w_T]
        REF = Annotated[W_Ref, w_reftype]

        if w_T is w_reftype.w_itemT:
            # convert 'raw_ref[T]' into 'T'
            irtag = IRTag("ptr.deref")

            @vm.register_builtin_func(w_reftype.fqn, "deref", irtag=irtag)
            def w_ptr_deref(vm: "SPyVM", w_ref: REF) -> T:
                addr = w_ref.addr
                return vm.call_generic(UNSAFE.w_mem_read, [w_T], [vm.wrap(addr)])

            return W_OpSpec(w_ptr_deref)

        else:
            return W_OpSpec.NULL

    @builtin_method("__call_method__", color="blue", kind="metafunc")
    @staticmethod
    def w_CALL_METHOD(
        vm: "SPyVM", wam_T: "W_MetaArg", wam_name: "W_MetaArg", *args_wam: "W_MetaArg"
    ) -> "W_OpSpec":
        ref_T = wam_T.w_static_T
        assert isinstance(ref_T, W_RefType)
        w_T = ref_T.w_itemT
        assert isinstance(w_T, W_Type)

        name = wam_name.blue_unwrap_str(vm)
        w_meth = w_T.lookup(name)
        if not isinstance(w_meth, W_ASTFunc):
            return W_OpSpec.NULL
        else:
            return W_OpSpec(w_meth, [wam_T, *args_wam])


@UNSAFE.builtin_func(color="blue")
def w_ptr_getfield(vm: "SPyVM", w_T: W_Type, w_memkind: W_Str) -> W_Dynamic:
    memkind = vm.unwrap_str(w_memkind)
    # fields can be returned "by value" or "by reference". Primitive types
    # returned by value, but struct types are always returned by reference
    # (i.e., we return a pointer to it).
    if w_T.is_struct(vm):
        w_ref_func = w_raw_ref if memkind == "raw" else w_gc_ref
        w_T = vm.fast_call(w_ref_func, [w_T])  # type: ignore
        by = "byref"
    else:
        by = "byval"

    T = Annotated[W_Object, w_T]

    # example FQNs:
    #     unsafe::ptr_getfield_byval[i32]
    #     unsafe::ptr_getfield_byref[raw_ref[Point]]
    #     unsafe::ptr_getfield_byref[gc_ref[Point]]
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
            assert isinstance(w_T, W_RefType)
            return W_Ref(w_T, addr, 1)
        else:
            return vm.call_generic(UNSAFE.w_mem_read, [w_T], [vm.wrap(addr)])

    return w_ptr_getfield_T


@UNSAFE.builtin_func(color="blue")
def w_ptr_setfield(vm: "SPyVM", w_T: W_Type) -> W_Dynamic:
    T = Annotated[W_Object, w_T]

    # example FQN: unsafe::ptr_setfield[i32]
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
