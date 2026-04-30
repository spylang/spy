import inspect
from typing import TYPE_CHECKING, Callable

from spy.errors import WIP
from spy.vm.b import B
from spy.vm.builtin import builtin_method
from spy.vm.modules.unsafe.ptr import W_Ptr
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.primitive import W_F64, W_I32
from spy.vm.registry import ModuleRegistry
from spy.vm.w import W_Func, W_FuncType, W_Object, W_Str

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

JSFFI = ModuleRegistry("jsffi")


@JSFFI.builtin_type("JsVal")
class W_JsVal(W_Object):
    @builtin_method("__convert_from__", color="blue", kind="metafunc")
    @staticmethod
    def w_CONVERT_FROM(
        vm: "SPyVM", wam_expT: W_MetaArg, wam_gotT: W_MetaArg, wam_x: W_MetaArg
    ) -> W_OpSpec:
        w_gotT = wam_gotT.w_blueval
        if w_gotT is B.w_f64:
            return W_OpSpec(JSFFI.w_jsval_from_f64)
        elif w_gotT is B.w_i32:
            return W_OpSpec(JSFFI.w_jsval_from_i32)
        elif w_gotT is B.w_str:
            return W_OpSpec(JSFFI.w_jsval_from_str)
        elif w_gotT.pyclass is W_JsRef:  # type: ignore
            return W_OpSpec(JSFFI.w_jsval_from_jsref)
        elif isinstance(w_gotT, W_FuncType):
            if w_gotT == W_FuncType.parse("def() -> None"):
                return W_OpSpec(JSFFI.w_jsval_from_func)
            elif w_gotT == W_FuncType.parse("def(f64) -> None"):
                return W_OpSpec(JSFFI.w_jsval_from_func_f64)
            else:
                raise WIP("Only simple callbacks are supported")
        else:
            return W_OpSpec.NULL


@JSFFI.builtin_type("JsRef")
class W_JsRef(W_Object):
    @builtin_method("__getattribute__")
    @staticmethod
    def w_getattribute(vm: "SPyVM", w_self: "W_JsRef", name: W_Str) -> "W_JsRef":
        raise NotImplementedError

    @builtin_method("__setattr__")
    @staticmethod
    def w_setattr(vm: "SPyVM", w_self: "W_JsRef", name: W_Str, val: W_JsVal) -> None:
        raise NotImplementedError

    @builtin_method("__call_method__", color="blue", kind="metafunc")
    @staticmethod
    def w_CALL_METHOD(
        vm: "SPyVM", wam_obj: W_MetaArg, wam_method: W_MetaArg, *args_wam: W_MetaArg
    ) -> W_OpSpec:
        n = len(args_wam)
        if n > 6:
            raise WIP(f"unsupported number of arguments for __call_method__: {n}")
        return W_OpSpec(getattr(JSFFI, f"w_js_call_method_{n}"))

    @builtin_method("__convert_from__", color="blue", kind="metafunc")
    @staticmethod
    def w_CONVERT_FROM(
        vm: "SPyVM", wam_expT: W_MetaArg, wam_gotT: W_MetaArg, wam_x: W_MetaArg
    ) -> W_OpSpec:
        w_gotT = wam_gotT.w_blueval
        if w_gotT is B.w_str:
            return W_OpSpec(JSFFI.w_js_string)
        elif w_gotT is B.w_i32:
            return W_OpSpec(JSFFI.w_js_i32)
        elif w_gotT is B.w_f64:
            return W_OpSpec(JSFFI.w_js_f64)
        else:
            return W_OpSpec.NULL

    @builtin_method("__convert_to__", color="blue", kind="metafunc")
    @staticmethod
    def w_CONVERT_TO(
        vm: "SPyVM", wam_expT: W_MetaArg, wam_gotT: W_MetaArg, wam_x: W_MetaArg
    ) -> W_OpSpec:
        w_expT = wam_expT.w_blueval
        if w_expT is B.w_i32:
            return W_OpSpec(JSFFI.w_js_to_f64)
        elif w_expT is B.w_f64:
            return W_OpSpec(JSFFI.w_js_to_i32)
        elif w_expT.pyclass is W_JsVal:  # type: ignore
            return W_OpSpec(JSFFI.w_jsval_from_jsref)
        else:
            raise WIP(f"Cannot convert a JsRef into a {w_expT}")


@JSFFI.builtin_func
def w_jsval_from_f64(vm: "SPyVM", w_x: W_F64) -> W_JsVal:
    raise NotImplementedError


@JSFFI.builtin_func
def w_jsval_from_i32(vm: "SPyVM", w_x: W_I32) -> W_JsVal:
    raise NotImplementedError


@JSFFI.builtin_func
def w_jsval_from_str(vm: "SPyVM", w_x: W_Str) -> W_JsVal:
    raise NotImplementedError


@JSFFI.builtin_func
def w_jsval_from_jsref(vm: "SPyVM", w_x: W_JsRef) -> W_JsVal:
    raise NotImplementedError


@JSFFI.builtin_func
def w_jsval_from_func(vm: "SPyVM", w_fn: W_Func) -> W_JsVal:
    raise NotImplementedError


@JSFFI.builtin_func
def w_jsval_from_func_f64(vm: "SPyVM", w_fn: W_Func) -> W_JsVal:
    raise NotImplementedError


@JSFFI.builtin_func
def w_request_animation_frame(vm: "SPyVM", w_fn: W_Func) -> None:
    # useful helper function equivalent to
    # jsffi.drop_ref(jsffi.get_GlobalThis().requestAnimationFrame(frame))
    raise NotImplementedError


#


@JSFFI.builtin_func
def w_debug(vm: "SPyVM", w_str: W_Str) -> None:
    s = vm.unwrap_str(w_str)
    print("[JSFFI debug]", s)


@JSFFI.builtin_func
def w_init(vm: "SPyVM") -> None:
    raise NotImplementedError


@JSFFI.builtin_func
def w__debug_n_jsrefs(vm: "SPyVM") -> W_I32:
    raise NotImplementedError


@JSFFI.builtin_func
def w_get_GlobalThis(vm: "SPyVM") -> W_JsRef:
    raise NotImplementedError


@JSFFI.builtin_func
def w_get_Console(vm: "SPyVM") -> W_JsRef:
    raise NotImplementedError


@JSFFI.builtin_func
def w_get_Document(vm: "SPyVM") -> W_JsRef:
    raise NotImplementedError


@JSFFI.builtin_func
def w_js_string(vm: "SPyVM", w_str: W_Str) -> W_JsRef:
    raise NotImplementedError


@JSFFI.builtin_func
def w_js_i32(vm: "SPyVM", w_i: W_I32) -> W_JsRef:
    raise NotImplementedError


@JSFFI.builtin_func
def w_js_f64(vm: "SPyVM", w_i: W_F64) -> W_JsRef:
    raise NotImplementedError


def _make_call_method(n: int) -> Callable[..., W_JsRef]:
    def w_js_call_method(vm: "SPyVM", *args: W_JsVal) -> W_JsRef:
        raise NotImplementedError

    P_OR_K = inspect.Parameter.POSITIONAL_OR_KEYWORD
    params = [inspect.Parameter("vm", P_OR_K, annotation="SPyVM")]
    params.append(inspect.Parameter("w_target", P_OR_K, annotation=W_JsRef))
    params.append(inspect.Parameter("name", P_OR_K, annotation=W_Str))
    for i in range(n):
        params.append(inspect.Parameter(f"arg{i}", P_OR_K, annotation=W_JsVal))
    w_js_call_method.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        params, return_annotation=W_JsRef
    )
    w_js_call_method.__name__ = f"w_js_call_method_{n}"
    return w_js_call_method


for _n in range(7):
    _fn = _make_call_method(_n)
    JSFFI.builtin_func(_fn)


@JSFFI.builtin_func
def w_drop_ref(vm: "SPyVM", w_target: W_JsRef) -> None:
    raise NotImplementedError


@JSFFI.builtin_func
def w_js_u8array_from_ptr(vm: "SPyVM", w_ptr: W_Ptr, w_length: W_I32) -> W_JsRef:
    raise NotImplementedError


@JSFFI.builtin_func
def w_js_new_ImageData(
    vm: "SPyVM", w_array: W_JsRef, w_width: W_I32, w_height: W_I32
) -> W_JsRef:
    raise NotImplementedError


@JSFFI.builtin_func
def w_js_to_i32(vm: "SPyVM", w_ref: W_JsRef) -> W_I32:
    raise NotImplementedError


@JSFFI.builtin_func
def w_js_to_f64(vm: "SPyVM", w_ref: W_JsRef) -> W_F64:
    raise NotImplementedError
