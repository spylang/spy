import sys
from typing import TYPE_CHECKING, Any

from spy.errors import SPyError
from spy.fqn import FQN
from spy.vm.builtin import builtin_method
from spy.vm.function import W_ASTFunc, W_Func
from spy.vm.object import W_Object
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.primitive import W_Bool, W_Dynamic
from spy.vm.str import W_Str

from . import SPY, interp_list

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@SPY.builtin_func(color="blue", kind="metafunc")
def w_COLOR(vm: "SPyVM", wam_obj: W_MetaArg) -> W_OpSpec:
    w_color = vm.wrap(wam_obj.color)
    return W_OpSpec.const(w_color)


@SPY.builtin_func(color="blue", kind="metafunc")
def w_as_red(vm: "SPyVM", wam_obj: W_MetaArg) -> W_OpSpec:
    vm.import_("_identity")
    w_T = wam_obj.w_static_T
    w_id_fn = vm.lookup_global(FQN("_identity::identity"))
    w_id_impl = vm.getitem_w(w_id_fn, w_T)
    assert isinstance(w_id_impl, W_Func)
    return W_OpSpec(w_id_impl)


@SPY.builtin_func
def w_is_compiled(vm: "SPyVM") -> W_Bool:
    from spy.vm.b import B

    return B.w_False


@SPY.builtin_func("__INIT__", color="blue")
def w_INIT(vm: "SPyVM") -> None:
    for w_listtype in interp_list.PREBUILT_INTERP_LIST_TYPES.values():
        w_listtype.register_push_function(vm)


@SPY.builtin_type("EmptyListType")
class W_EmptyListType(W_Object):
    """
    An object representing '[]'
    """

    def __init__(self) -> None:
        raise Exception("You cannot instantiate W_EmptyListType")

    def __repr__(self) -> str:
        return "<spy empty_list []>"

    def spy_unwrap(self, vm: "SPyVM") -> Any:
        return []

    @builtin_method("__call_method__", color="blue", kind="metafunc")
    @staticmethod
    def w_CALL_METHOD(
        vm: "SPyVM",
        wam_self: "W_MetaArg",
        wam_name: "W_MetaArg",
        *args_wam: "W_MetaArg",
    ) -> "W_OpSpec":
        name = wam_name.blue_unwrap_str(vm)
        if name in ("append", "extend", "insert"):
            err = SPyError("W_TypeError", "cannot mutate an untyped empty list")
            err.add("error", "this is untyped", wam_self.loc)
            if sym := wam_self.sym:
                err.add(
                    "note",
                    f"help: use an explicit type: `{sym.name}: list[T] = []`",
                    sym.loc,
                )
            raise err
        return W_OpSpec.NULL


@SPY.builtin_type("EmptyDictType")
class W_EmptyDictType(W_Object):
    """
    An object representing '{}'
    """

    def __init__(self) -> None:
        raise Exception("You cannot instantiate W_EmptyDictType")

    def __repr__(self) -> str:
        return "<spy empty_dict {}>"

    def spy_unwrap(self, vm: "SPyVM") -> Any:
        return {}


SPY.add("empty_list", W_EmptyListType.__new__(W_EmptyListType))
SPY.add("empty_dict", W_EmptyDictType.__new__(W_EmptyDictType))


@SPY.builtin_func(color="blue")
def w_force_inline(vm: "SPyVM", w_func: W_Object) -> W_Object:
    from spy.force_inline import validate_force_inline

    if not isinstance(w_func, W_ASTFunc):
        err = SPyError(
            "W_TypeError",
            "@force_inline can only be applied to def'd functions",
        )
        raise err
    if w_func.color != "red":
        err = SPyError(
            "W_TypeError",
            "@force_inline cannot be applied to @blue functions",
        )
        err.add("error", "this is not a red function", w_func.def_loc)
        raise err
    validate_force_inline(w_func)
    w_func.is_force_inline = True
    return w_func


@SPY.builtin_func
def w__stdout_write(vm: "SPyVM", w_s: W_Str) -> None:
    sys.stdout.write(vm.unwrap(w_s))


@SPY.builtin_func(color="blue")
def w_lookup_fqn(vm: "SPyVM", w_s: W_Str) -> W_Dynamic:
    fqn_str = vm.unwrap_str(w_s)
    fqn = FQN(fqn_str)
    vm.import_(fqn.modname)
    w_val = vm.lookup_global_maybe(fqn)
    if w_val is None:
        raise SPyError("W_ValueError", f"FQN not found: {fqn_str}")
    return w_val
