from typing import TYPE_CHECKING

from spy.vm.b import B
from spy.vm.builtin import builtin_method
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.primitive import W_I32
from spy.vm.registry import ModuleRegistry
from spy.vm.w import W_Func, W_FuncType, W_Object, W_Str, W_Type

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

JSFFI = ModuleRegistry("jsffi")


@JSFFI.builtin_type("JsRef")
class W_JsRef(W_Object):
    @builtin_method("__getattribute__")
    @staticmethod
    def w_getattribute(vm: "SPyVM", w_self: "W_JsRef", name: W_Str) -> "W_JsRef":
        raise NotImplementedError

    @builtin_method("__setattr__")
    @staticmethod
    def w_setattr(vm: "SPyVM", w_self: "W_JsRef", name: W_Str, val: "W_JsRef") -> None:
        raise NotImplementedError

    @builtin_method("__call_method__", color="blue", kind="metafunc")
    @staticmethod
    def w_CALL_METHOD(
        vm: "SPyVM", wam_obj: W_MetaArg, wam_method: W_MetaArg, *args_wam: W_MetaArg
    ) -> W_OpSpec:
        n = len(args_wam)
        if n == 1:
            return W_OpSpec(JSFFI.w_js_call_method_1)
        else:
            raise Exception(f"unsupported number of arguments for __call_method__: {n}")

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
        elif isinstance(w_gotT, W_FuncType):
            assert w_gotT == W_FuncType.parse("def() -> None")
            return W_OpSpec(JSFFI.w_js_wrap_func)
        else:
            return W_OpSpec.NULL


@JSFFI.builtin_func
def w_debug(vm: "SPyVM", w_str: W_Str) -> None:
    s = vm.unwrap_str(w_str)
    print("[JSFFI debug]", s)


@JSFFI.builtin_func
def w_init(vm: "SPyVM") -> None:
    raise NotImplementedError


@JSFFI.builtin_func
def w_get_GlobalThis(vm: "SPyVM") -> W_JsRef:
    raise NotImplementedError


@JSFFI.builtin_func
def w_get_Console(vm: "SPyVM") -> W_JsRef:
    raise NotImplementedError


@JSFFI.builtin_func
def w_js_string(vm: "SPyVM", w_str: W_Str) -> W_JsRef:
    raise NotImplementedError


@JSFFI.builtin_func
def w_js_i32(vm: "SPyVM", w_i: W_I32) -> W_JsRef:
    raise NotImplementedError


@JSFFI.builtin_func
def w_js_wrap_func(vm: "SPyVM", w_fn: W_Func) -> W_JsRef:
    raise NotImplementedError


@JSFFI.builtin_func
def w_js_call_method_1(
    vm: "SPyVM", w_target: W_JsRef, name: W_Str, arg0: W_JsRef
) -> W_JsRef:
    raise NotImplementedError
