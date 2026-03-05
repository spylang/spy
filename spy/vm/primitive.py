from ctypes import c_float as float32
from typing import TYPE_CHECKING, Annotated

import fixedint

from spy.fqn import FQN
from spy.vm.b import OP, TYPES, B
from spy.vm.builtin import builtin_method
from spy.vm.object import W_Object, W_Type

# fixedint/__init__.pyi overrides FixedInt and mypy thinks it's a
# function. Let's convince it back that it's a type
if TYPE_CHECKING:
    from fixedint import _FixedInt as FixedInt
else:
    from fixedint import FixedInt

if TYPE_CHECKING:
    from spy.vm.opspec import W_MetaArg, W_OpSpec
    from spy.vm.str import W_Str
    from spy.vm.vm import SPyVM


@TYPES.builtin_type("NoneType", lazy_definition=True)
class W_NoneType(W_Object):
    """
    This is a singleton: there should be only one instance of this class,
    which is w_None.
    """

    def __init__(self) -> None:
        # this is just a sanity check: we don't want people to be able to
        # create additional <None>s
        raise Exception("You cannot instantiate W_NoneType")

    def __repr__(self) -> str:
        return "<spy None>"

    def spy_unwrap(self, vm: "SPyVM") -> None:
        return None

    @builtin_method("__str__", color="blue", kind="metafunc")
    @staticmethod
    def w_STR(vm: "SPyVM", wam_self: "W_MetaArg") -> "W_OpSpec":
        from spy.vm.opspec import W_OpSpec

        return W_OpSpec.const(vm.wrap("None"))


B.add("None", W_NoneType.__new__(W_NoneType))


@B.builtin_type("i32", lazy_definition=True)
class W_I32(W_Object):
    __spy_storage_category__ = "value"
    value: fixedint.Int32

    def __init__(self, value: int | FixedInt) -> None:
        self.value = fixedint.Int32(value)

    @builtin_method("__new__", color="blue", kind="metafunc")
    @staticmethod
    def w_NEW(vm: "SPyVM", wam_cls: "W_MetaArg", *args_wam: "W_MetaArg") -> "W_OpSpec":
        from spy.vm.opspec import W_OpSpec

        if len(args_wam) != 1:
            return W_OpSpec.NULL
        wam_arg = args_wam[0]
        if wam_arg.w_static_T == B.w_f64:
            return W_OpSpec(OP.w_f64_to_i32, [wam_arg])
        elif wam_arg.w_static_T == B.w_f32:
            return W_OpSpec(OP.w_f32_to_i32, [wam_arg])
        elif wam_arg.w_static_T == B.w_str:
            return W_OpSpec(OP.w_str_to_i32, [wam_arg])
        return W_OpSpec.NULL

    def __repr__(self) -> str:
        return f"W_I32({self.value})"

    def spy_unwrap(self, vm: "SPyVM") -> fixedint.Int32:
        return self.value

    def spy_key(self, vm: "SPyVM") -> fixedint.Int32:
        return self.value

    @builtin_method("__str__")
    @staticmethod
    def w_str(vm: "SPyVM", w_self: "W_I32") -> "W_Str":
        i = vm.unwrap_i32(w_self)
        return vm.wrap(str(i))

    # XXX: why do we need an explicit __repr__? In theory the __str__ should be
    # automatically used, but it's not
    @builtin_method("__repr__")
    @staticmethod
    def w_repr(vm: "SPyVM", w_self: "W_I32") -> "W_Str":
        i = vm.unwrap_i32(w_self)
        return vm.wrap(str(i))


@B.builtin_type("u32", lazy_definition=True)
class W_U32(W_Object):
    __spy_storage_category__ = "value"
    value: fixedint.UInt32

    def __init__(self, value: int | FixedInt) -> None:
        self.value = fixedint.UInt32(value)

    @builtin_method("__new__", color="blue", kind="metafunc")
    @staticmethod
    def w_NEW(vm: "SPyVM", wam_cls: "W_MetaArg", *args_wam: "W_MetaArg") -> "W_OpSpec":
        from spy.vm.opspec import W_OpSpec

        if len(args_wam) != 1:
            return W_OpSpec.NULL
        wam_arg = args_wam[0]
        if wam_arg.w_static_T == B.w_str:
            return W_OpSpec(OP.w_str_to_u32, [wam_arg])
        return W_OpSpec.NULL

    def __repr__(self) -> str:
        return f"W_U32({self.value})"

    def spy_unwrap(self, vm: "SPyVM") -> fixedint.UInt32:
        return self.value

    def spy_key(self, vm: "SPyVM") -> fixedint.UInt32:
        return self.value

    @builtin_method("__str__")
    @staticmethod
    def w_str(vm: "SPyVM", w_self: "W_U32") -> "W_Str":
        i = vm.unwrap(w_self)
        return vm.wrap(str(i))

    @builtin_method("__repr__")
    @staticmethod
    def w_repr(vm: "SPyVM", w_self: "W_U32") -> "W_Str":
        i = vm.unwrap(w_self)
        return vm.wrap(str(i))


@B.builtin_type("i8", lazy_definition=True)
class W_I8(W_Object):
    __spy_storage_category__ = "value"
    value: fixedint.Int8

    def __init__(self, value: int | FixedInt) -> None:
        self.value = fixedint.Int8(value)

    @builtin_method("__new__", color="blue", kind="metafunc")
    @staticmethod
    def w_NEW(vm: "SPyVM", wam_cls: "W_MetaArg", *args_wam: "W_MetaArg") -> "W_OpSpec":
        from spy.vm.opspec import W_OpSpec

        if len(args_wam) != 1:
            return W_OpSpec.NULL
        wam_arg = args_wam[0]
        if wam_arg.w_static_T == B.w_str:
            return W_OpSpec(OP.w_str_to_i8, [wam_arg])
        return W_OpSpec.NULL

    def __repr__(self) -> str:
        return f"W_I8({self.value})"

    def spy_unwrap(self, vm: "SPyVM") -> fixedint.Int8:
        return self.value

    def spy_key(self, vm: "SPyVM") -> fixedint.Int8:
        return self.value

    @builtin_method("__str__")
    @staticmethod
    def w_str(vm: "SPyVM", w_self: "W_I8") -> "W_Str":
        i = vm.unwrap(w_self)
        return vm.wrap(str(i))


@B.builtin_type("u8", lazy_definition=True)
class W_U8(W_Object):
    __spy_storage_category__ = "value"
    value: fixedint.UInt8

    def __init__(self, value: int | FixedInt) -> None:
        self.value = fixedint.UInt8(value)

    @builtin_method("__new__", color="blue", kind="metafunc")
    @staticmethod
    def w_NEW(vm: "SPyVM", wam_cls: "W_MetaArg", *args_wam: "W_MetaArg") -> "W_OpSpec":
        from spy.vm.opspec import W_OpSpec

        if len(args_wam) != 1:
            return W_OpSpec.NULL
        wam_arg = args_wam[0]
        if wam_arg.w_static_T == B.w_str:
            return W_OpSpec(OP.w_str_to_u8, [wam_arg])
        return W_OpSpec.NULL

    def __repr__(self) -> str:
        return f"W_U8({self.value})"

    def spy_unwrap(self, vm: "SPyVM") -> fixedint.UInt8:
        return self.value

    def spy_key(self, vm: "SPyVM") -> fixedint.UInt8:
        return self.value

    @builtin_method("__str__")
    @staticmethod
    def w_str(vm: "SPyVM", w_self: "W_U8") -> "W_Str":
        u = vm.unwrap(w_self)
        return vm.wrap(str(u))


@B.builtin_type("f64", lazy_definition=True)
class W_F64(W_Object):
    __spy_storage_category__ = "value"
    value: float

    def __init__(self, value: float) -> None:
        assert type(value) is float
        self.value = value

    @builtin_method("__new__", color="blue", kind="metafunc")
    @staticmethod
    def w_NEW(vm: "SPyVM", wam_cls: "W_MetaArg", *args_wam: "W_MetaArg") -> "W_OpSpec":
        from spy.vm.opspec import W_OpSpec

        if len(args_wam) != 1:
            return W_OpSpec.NULL
        wam_arg = args_wam[0]
        if wam_arg.w_static_T == B.w_i32:
            return W_OpSpec(OP.w_i32_to_f64, [wam_arg])
        elif wam_arg.w_static_T == B.w_f32:
            return W_OpSpec(OP.w_f32_to_f64, [wam_arg])
        return W_OpSpec.NULL

    def __repr__(self) -> str:
        return f"W_F64({self.value})"

    def spy_unwrap(self, vm: "SPyVM") -> float:
        return self.value

    def spy_key(self, vm: "SPyVM") -> float:
        return self.value

    @builtin_method("__str__")
    @staticmethod
    def w_str(vm: "SPyVM", w_self: "W_F64") -> "W_Str":
        f = vm.unwrap_f64(w_self)
        return vm.wrap(str(f))


@B.builtin_type("f32", lazy_definition=True)
class W_F32(W_Object):
    __spy_storage_category__ = "value"
    value: float32

    def __init__(self, value: float | float32) -> None:
        self.value = float32(value) if type(value) is float else value  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"W_F32({self.value.value:.7g})"

    def spy_unwrap(self, vm: "SPyVM") -> float:
        return self.value.value

    def spy_key(self, vm: "SPyVM") -> float:
        return self.value.value

    @builtin_method("__str__")
    @staticmethod
    def w_str(vm: "SPyVM", w_self: "W_F32") -> "W_Str":
        f = vm.unwrap_f32(w_self)
        return vm.wrap(f"{f:.7g}")


@B.builtin_type("bool", lazy_definition=True)
class W_Bool(W_Object):
    __spy_storage_category__ = "value"
    value: bool

    def __init__(self, value: bool) -> None:
        # this is just a sanity check: we don't want people to be able to
        # create additional instances of W_Bool
        raise Exception("You cannot instantiate W_Bool. Use vm.wrap().")

    @staticmethod
    def _make_singleton(value: bool) -> "W_Bool":
        w_obj = W_Bool.__new__(W_Bool)
        w_obj.value = value
        return w_obj

    def __repr__(self) -> str:
        return f"W_Bool({self.value})"

    def spy_unwrap(self, vm: "SPyVM") -> bool:
        return self.value

    def spy_key(self, vm: "SPyVM") -> bool:
        return self.value

    def not_(self, vm: "SPyVM") -> "W_Bool":
        if self.value:
            return B.w_False
        else:
            return B.w_True

    @builtin_method("__str__")
    @staticmethod
    def w_str(vm: "SPyVM", w_self: "W_Bool") -> "W_Str":
        b = vm.unwrap(w_self)
        return vm.wrap(str(b))


B.add("True", W_Bool._make_singleton(True))
B.add("False", W_Bool._make_singleton(False))


@TYPES.builtin_type("NotImplementedType", lazy_definition=True)
class W_NotImplementedType(W_Object):
    def __init__(self) -> None:
        # this is just a sanity check: we don't want people to be able to
        # create additional instances
        raise Exception("You cannot instantiate W_NotImplementedType")

    @builtin_method("__str__", color="blue", kind="metafunc")
    @staticmethod
    def w_STR(vm: "SPyVM", wam_self: "W_MetaArg") -> "W_OpSpec":
        from spy.vm.opspec import W_OpSpec

        return W_OpSpec.const(vm.wrap("NotImplemented"))


B.add("NotImplemented", W_NotImplementedType.__new__(W_NotImplementedType))


# The <dynamic> type
# ===================
#
# <dynamic> is special:
#
# - it's not a real type, in the sense that you cannot have an instance whose
#   type is `dynamic`
#
# - every class is considered to be a subclass of <dynamic>
#
# - conversion from T to <dynamic> always succeeds (like from T to <object>)
#
# - conversion from <dynamic> to T is always possible but it might fail at
#   runtime (like from <object> to T)
#
# From some point of view, <dynamic> is the twin of <object>, because it acts
# as if it were at the root of the type hierarchy. The biggest difference is
# how operators are dispatched: operations on <object> almost never succeeds,
# while operations on <dynamic> are dispatched to the actual dynamic
# types. For example:
#
#    x: object = 1
#    y: dynamic = 2
#    z: dynamic = 'hello'
#
#    x + 1 # compile-time error: cannot do `<object> + <i32>`
#    y + 1 # succeeds, but the dispatch is done at runtime
#    z + 1 # runtime error: cannot do `<i32> + <str>`
#
# Since it's a compile-time only concept, W_Dynamic is not a pyclass, but it's
# just an annotated version of W_Object, which @builtin_func knows how to deal
# with.

w_DynamicType = W_Type.declare(FQN("builtins::dynamic"))
B.add("dynamic", w_DynamicType)
W_Dynamic = Annotated[W_Object, B.w_dynamic]
