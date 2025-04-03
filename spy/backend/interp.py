"""
SPy 'interp' backend.

This is useful only for tests. Expose interp-level W_Modules and W_Funtions as
Python objects which can be accessed and called by tests.

The SPy code is interpreted by the SPy VM.

Python objects are automatically converted into their SPy equivalent and
vice-versa, by using vm.wrap and vm.unwrap.
"""
from typing import Any
import fixedint
from spy.vm.vm import SPyVM
from spy.vm.module import W_Module
from spy.vm.function import W_Func, W_FuncType
from spy.vm.b import B


class InterpModuleWrapper:
    """
    Wrap a W_Module.
    """
    vm: SPyVM
    w_mod: W_Module

    def __init__(self, vm: SPyVM, w_mod: W_Module) -> None:
        self.vm = vm
        self.w_mod = w_mod

    def __dir__(self) -> list[str]:
        return [fqn.symbol_name for fqn in self.w_mod.keys()]

    def __getattr__(self, attr: str) -> Any:
        w_obj = self.w_mod.getattr(attr)
        if isinstance(w_obj, W_Func):
            return InterpFuncWrapper(self.vm, w_obj)
        return self.vm.unwrap(w_obj)


class InterpFuncWrapper:
    """
    Wrap a W_Func.
    """
    vm: SPyVM
    w_func: W_Func
    w_functype: W_FuncType

    def __init__(self, vm: SPyVM, w_func: W_Func):
        self.vm = vm
        self.w_func = w_func
        self.w_functype = w_func.w_functype

    def __call__(self, *args: Any, unwrap: bool = True) -> Any:
        # *args contains python-level objs. We want to wrap them into args_w
        # *and to call the func, and unwrap the result
        args_w = []
        for arg, param in zip(args, self.w_functype.params, strict=True):
            w_type = param.w_type
            if w_type is B.w_i8:
                arg = fixedint.Int8(arg)
            elif w_type is B.w_u8:
                arg = fixedint.UInt8(arg)
            w_arg = self.vm.wrap(arg)
            args_w.append(w_arg)

        w_res = self.vm.fast_call(self.w_func, args_w)
        if unwrap:
            return self.vm.unwrap(w_res)
        else:
            return w_res
