from typing import TYPE_CHECKING, Any

from spy.errors import SPyError
from spy.fqn import FQN
from spy.vm.builtin import builtin_method
from spy.vm.function import W_ASTFunc, W_FuncType
from spy.vm.object import W_Object, W_Type
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.primitive import W_Dynamic

from . import UNSAFE

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


def _signature_matches(w_expT: "W_CFuncPtrType", w_gotT: W_FuncType) -> bool:
    if len(w_expT.w_argtypes_w) != len(w_gotT.params):
        return False
    for w_exp_arg, param in zip(w_expT.w_argtypes_w, w_gotT.params):
        if w_exp_arg is not param.w_T:
            return False
    return w_expT.w_restype is w_gotT.w_restype


class W_CFuncPtr(W_Object):
    """
    Value class for c_func_ptr[R, A0, ...] instances.

    In the C backend, no boxing occurs: a c_func_ptr value lowers to the bare
    C symbol name of the SPy function (via W_OpSpec.const and
    fmt_expr_FQNConst). This class exists so W_CFuncPtrType has a valid
    pyclass, and to host __convert_from__ so it is registered into each
    type instance's dict_w by W_Type.define().
    """

    __spy_storage_category__ = "value"

    # At the interp level a c_func_ptr carries the underlying W_Func.
    w_func: W_ASTFunc
    w_cfuncptr_T: "W_CFuncPtrType"

    def __init__(self, w_cfuncptr_T: "W_CFuncPtrType", w_func: W_ASTFunc) -> None:
        self.w_cfuncptr_T = w_cfuncptr_T
        self.w_func = w_func

    def spy_get_w_type(self, vm: "SPyVM") -> W_Type:
        return self.w_cfuncptr_T

    def spy_key(self, vm: "SPyVM") -> Any:
        return ("c_func_ptr", self.w_func.fqn)

    def __repr__(self) -> str:
        return f"W_CFuncPtr({self.w_func.fqn})"

    @builtin_method("__convert_from__", color="blue", kind="metafunc")
    @staticmethod
    def w_CONVERT_FROM(
        vm: "SPyVM", wam_expT: W_MetaArg, wam_gotT: W_MetaArg, wam_x: W_MetaArg
    ) -> W_OpSpec:
        w_expT = wam_expT.w_blueval
        assert isinstance(w_expT, W_CFuncPtrType)
        w_gotT = wam_gotT.w_blueval

        # only accept SPy functions as the source
        if not isinstance(w_gotT, W_FuncType):
            return W_OpSpec.NULL

        w_func = wam_x.w_blueval

        # the function must be a top-level red function
        if not isinstance(w_func, W_ASTFunc):
            raise SPyError(
                "W_TypeError",
                "@c_callback / c_func_ptr conversion requires a def'd function",
            )
        if w_func.color != "red":
            err = SPyError(
                "W_TypeError",
                "c_func_ptr conversion requires a red (non-@blue) function",
            )
            err.add("error", "this is not a red function", w_func.def_loc)
            raise err

        # signature must match structurally
        if not _signature_matches(w_expT, w_gotT):
            return W_OpSpec.NULL

        # Wrap in W_CFuncPtr so the interp-level return type matches.
        # In the C backend, fmt_expr_FQNConst for W_CFuncPtr emits the bare
        # symbol name — a function pointer value requires no boxing.
        return W_OpSpec.const(W_CFuncPtr(w_expT, w_func))


@UNSAFE.builtin_type("_c_func_ptr_type")
class W_CFuncPtrType(W_Type):
    """
    The metatype for c_func_ptr[R, A0, ...].

    Each distinct (R, A...) combination produces one W_CFuncPtrType instance,
    interned by FQN in _CACHE so that the same signature always yields the
    same Python object regardless of where or when it is constructed.
    At the C level, the type lowers to a typedef of the form:

        typedef R (*name)(A...);

    emitted into spy_structdefs.h by cstructwriter.
    """

    _CACHE: "dict[FQN, W_CFuncPtrType]" = {}

    w_restype: W_Type
    w_argtypes_w: list[W_Type]

    @classmethod
    def from_signature(
        cls, fqn: FQN, w_restype: W_Type, w_argtypes_w: list[W_Type]
    ) -> "W_CFuncPtrType":
        if fqn in cls._CACHE:
            return cls._CACHE[fqn]
        # from_pyclass(fqn, W_CFuncPtr) calls define(W_CFuncPtr), which scans
        # W_CFuncPtr.__dict__ and registers all @builtin_method entries
        # (including __convert_from__) into this type instance's dict_w.
        w_T = cls.from_pyclass(fqn, W_CFuncPtr)
        w_T.w_restype = w_restype
        w_T.w_argtypes_w = w_argtypes_w
        cls._CACHE[fqn] = w_T
        return w_T


@UNSAFE.builtin_func(color="blue", kind="generic")
def w_c_func_ptr(vm: "SPyVM", w_R: W_Type, *w_argtypes: W_Type) -> W_Dynamic:
    """
    c_func_ptr[R, A0, A1, ...] — a C function-pointer type.

    The first subscript argument is the return type; the remaining arguments
    are the parameter types, e.g.:
        c_func_ptr[bool, i32, i32]   # bool (*)(int32_t, int32_t)
        c_func_ptr[void]             # void (*)(void)
    """
    for i, w_a in enumerate(w_argtypes):
        if not isinstance(w_a, W_Type):
            raise SPyError(
                "W_TypeError",
                f"c_func_ptr argument type at position {i} must be a type, "
                f"got {w_a!r}",
            )
    w_argtypes_w = list(w_argtypes)
    fqn = FQN("unsafe").join("c_func_ptr", [w_R.fqn] + [w.fqn for w in w_argtypes_w])
    return W_CFuncPtrType.from_signature(fqn, w_R, w_argtypes_w)


@UNSAFE.builtin_func(color="blue")
def w_c_callback(vm: "SPyVM", w_func: W_Object) -> W_Object:
    """
    @c_callback — a no-op decorator that documents intent and validates that
    a function is suitable as a C callback: must be a red def'd function.

    The actual type conversion is performed by __convert_from__ above.
    """
    if not isinstance(w_func, W_ASTFunc):
        raise SPyError(
            "W_TypeError",
            "@c_callback can only be applied to def'd functions",
        )
    if w_func.color != "red":
        err = SPyError(
            "W_TypeError",
            "@c_callback cannot be applied to @blue functions",
        )
        err.add("error", "this is not a red function", w_func.def_loc)
        raise err
    return w_func
