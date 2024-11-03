from typing import TYPE_CHECKING
import struct
from spy.fqn import QN
from spy.vm.b import B
from spy.vm.object import spytype, Member, Annotated
from spy.vm.w import (W_Func, W_Type, W_Object, W_I32, W_F64, W_Void, W_Str,
                      W_Dynamic, W_List, W_FuncType)
from spy.vm.list import W_List
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.builtin import builtin_func
from spy.vm.registry import ModuleRegistry
from spy.vm.modules.types import W_TypeDef

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

JSFFI = ModuleRegistry('jsffi')

@JSFFI.spytype('JsRef')
class W_JsRef(W_Object):

    @staticmethod
    def op_GETATTR(vm: 'SPyVM', wop_obj: W_OpArg,
                   wop_attr: W_OpArg) -> W_OpImpl:
        return W_OpImpl(JSFFI.w_js_getattr)

    @staticmethod
    def op_SETATTR(vm: 'SPyVM', wop_obj: W_OpArg, wop_attr: W_OpArg,
                   wop_v: W_OpArg) -> W_OpImpl:
        return W_OpImpl(JSFFI.w_js_setattr)

    @staticmethod
    def op_CALL_METHOD(vm: 'SPyVM', wop_obj: W_OpArg, wop_method: W_OpArg,
                       w_opargs: W_List[W_OpArg]) -> W_OpImpl:
        args_wop = w_opargs.items_w
        n = len(args_wop)
        if n == 1:
            return W_OpImpl(JSFFI.w_js_call_method_1)
        else:
            raise Exception(
                f"unsupported number of arguments for CALL_METHOD: {n}"
            )

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
def w_js_wrap_func(vm: 'SPyVM', w_fn: W_Func) -> W_JsRef:
    raise NotImplementedError

@JSFFI.builtin_func
def w_js_call_method_1(vm: 'SPyVM', w_target: W_JsRef,
                     name: W_Str, arg0: W_JsRef) -> W_JsRef:
    raise NotImplementedError

@JSFFI.builtin_func
def w_js_getattr(vm: 'SPyVM', w_target: W_JsRef, name: W_Str) -> W_JsRef:
    raise NotImplementedError

@JSFFI.builtin_func
def w_js_setattr(vm: 'SPyVM', w_target: W_JsRef,
               name: W_Str, val: W_JsRef) -> None:
    raise NotImplementedError
