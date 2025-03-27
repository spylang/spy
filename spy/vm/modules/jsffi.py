from typing import TYPE_CHECKING, Annotated
import struct
from spy.vm.primitive import W_F64, W_I32, W_Dynamic, W_Void
from spy.vm.b import B
from spy.vm.object import Member
from spy.vm.w import W_Func, W_Type, W_Object, W_Str, W_FuncType
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.builtin import builtin_func, builtin_type, builtin_method
from spy.vm.registry import ModuleRegistry

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

JSFFI = ModuleRegistry('jsffi')

@JSFFI.builtin_type('JsRef')
class W_JsRef(W_Object):

    @builtin_method('__getattr__')
    @staticmethod
    def w_getattr(vm: 'SPyVM', w_self: 'W_JsRef', name: W_Str) -> 'W_JsRef':
        raise NotImplementedError

    @builtin_method('__setattr__')
    @staticmethod
    def w_setattr(vm: 'SPyVM', w_self: 'W_JsRef',
                  name: W_Str, val: 'W_JsRef') -> None:
        raise NotImplementedError

    @builtin_method('__CALL_METHOD__', color='blue')
    @staticmethod
    def w_CALL_METHOD(vm: 'SPyVM', wop_obj: W_OpArg, wop_method: W_OpArg,
                      *args_wop: W_OpArg) -> W_OpImpl:
        n = len(args_wop)
        if n == 1:
            return W_OpImpl(JSFFI.w_js_call_method_1)
        else:
            raise Exception(
                f"unsupported number of arguments for CALL_METHOD: {n}"
            )

    @builtin_method('__CONVERT_FROM__', color='blue')
    @staticmethod
    def w_CONVERT_FROM(vm: 'SPyVM', w_T: W_Type, wop_x: W_OpArg) -> W_OpImpl:
        if w_T is B.w_str:
            return W_OpImpl(JSFFI.w_js_string)
        elif w_T is B.w_i32:
            return W_OpImpl(JSFFI.w_js_i32)
        elif isinstance(w_T, W_FuncType):
            assert w_T == W_FuncType.parse('def() -> void')
            return W_OpImpl(JSFFI.w_js_wrap_func)
        else:
            return W_OpImpl.NULL


@JSFFI.builtin_func
def w_debug(vm: 'SPyVM', w_str: W_Str) -> None:
    s = vm.unwrap_str(w_str)
    print('[JSFFI debug]', s)

@JSFFI.builtin_func
def w_init(vm: 'SPyVM') -> None:
    raise NotImplementedError

@JSFFI.builtin_func
def w_get_GlobalThis(vm: 'SPyVM') -> W_JsRef:
    raise NotImplementedError

@JSFFI.builtin_func
def w_get_Console(vm: 'SPyVM') -> W_JsRef:
    raise NotImplementedError

@JSFFI.builtin_func
def w_js_string(vm: 'SPyVM', w_str: W_Str) -> W_JsRef:
    raise NotImplementedError

@JSFFI.builtin_func
def w_js_i32(vm: 'SPyVM', w_i: W_I32) -> W_JsRef:
    raise NotImplementedError

@JSFFI.builtin_func
def w_js_wrap_func(vm: 'SPyVM', w_fn: W_Func) -> W_JsRef:
    raise NotImplementedError

@JSFFI.builtin_func
def w_js_call_method_1(vm: 'SPyVM', w_target: W_JsRef,
                     name: W_Str, arg0: W_JsRef) -> W_JsRef:
    raise NotImplementedError
