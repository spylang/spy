"""
SPy 'interp' backend.

This is useful only for tests. Expose interp-level W_Modules and W_Funtions as
Python objects which can be accessed and called by tests.

The SPy code is interpreted by the SPy VM.

Python objects are automatically converted into their SPy equivalent and
vice-versa, by using vm.wrap and vm.unwrap.
"""
from typing import Any
from spy.vm.vm import SPyVM
from spy.vm.module import W_Module
from spy.vm.function import W_Function


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
        return list(self.w_mod.content.types_w.keys())

    def __getattr__(self, attr: str) -> Any:
        w_obj = self.w_mod.getattr(attr)
        if isinstance(w_obj, W_Function):
            return InterpFuncWrapper(self.vm, w_obj)
        return self.vm.unwrap(w_obj)


class InterpFuncWrapper:
    """
    Wrap a W_Function.
    """
    vm: SPyVM
    w_func: W_Function

    def __init__(self, vm: SPyVM, w_func: W_Function):
        self.vm = vm
        self.w_func = w_func

    def dis(self) -> None:
        self.w_func.w_code.pp()

    def __call__(self, *args: Any) -> Any:
        # *args contains python-level objs. We want to wrap them into args_w
        # *and to call the func, and unwrap the result
        args_w = [self.vm.wrap(arg) for arg in args]
        w_res = self.vm.call_function(self.w_func, args_w)
        return self.vm.unwrap(w_res)
