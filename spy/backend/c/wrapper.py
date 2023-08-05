import struct
from typing import Any, Optional
import py.path
import wasmtime
from spy.llwasm import LLWasmType
from spy.libspy import LLSPyInstance
from spy.vm.object import W_Type
from spy.vm.str import ll_spy_Str_new
from spy.vm.module import W_Module
from spy.vm.function import W_Function, W_FunctionType
from spy.vm.vm import SPyVM


class WasmModuleWrapper:
    vm: SPyVM
    w_mod: W_Module
    ll: LLSPyInstance

    def __init__(self, vm: SPyVM, w_mod: W_Module, f: py.path.local) -> None:
        self.vm = vm
        self.w_mod = w_mod
        self.ll = LLSPyInstance.from_file(f)

    def __repr__(self) -> str:
        return f"<WasmModuleWrapper 'self.ll.name'>"

    def __getattr__(self, name: str) -> Any:
        wasm_obj = self.ll.get_export(name)
        if isinstance(wasm_obj, wasmtime.Func):
            return self.read_function(name)
        elif isinstance(wasm_obj, wasmtime.Global):
            return self.read_global(name)
        else:
            t = type(wasm_obj)
            raise NotImplementedError(f'Unknown WASM object: {t}')

    def read_function(self, name: str) -> 'WasmFuncWrapper':
        w_func = self.w_mod.content.get(name)
        assert isinstance(w_func, W_Function)
        return WasmFuncWrapper(self.vm, self.ll, name, w_func.w_functype)

    def read_global(self, name: str) -> Any:
        w_type = self.w_mod.content.types_w[name]
        t: LLWasmType
        if w_type is self.vm.builtins.w_i32:
            t = 'int32_t'
        else:
            assert False, f'Unknown type: {w_type}'

        return self.ll.read_global(name, deref=t)


class WasmFuncWrapper:
    vm: SPyVM
    ll: LLSPyInstance
    name: str
    w_functype: W_FunctionType

    def __init__(self, vm: SPyVM, ll: LLSPyInstance, name:str,
                 w_functype: W_FunctionType) -> None:
        self.vm = vm
        self.ll = ll
        self.name = name
        self.w_functype = w_functype

    def py2wasm(self, pyval: Any, w_type: W_Type) -> Any:
        b = self.vm.builtins
        if w_type is b.w_i32:
            return pyval
        elif w_type is b.w_str:
            # XXX: with the GC, we need to think how to keep this alive
            return ll_spy_Str_new(self.ll, pyval)
        else:
            assert False, f'Unsupported type: {w_type}'

    def from_py_args(self, py_args: Any) -> Any:
        a = len(py_args)
        b = len(self.w_functype.params)
        if a != b:
            raise TypeError(f'{self.name}: expected {b} arguments, got {a}')
        #
        wasm_args = []
        for py_arg, param in zip(py_args, self.w_functype.params):
            wasm_arg = self.py2wasm(py_arg, param.w_type)
            wasm_args.append(wasm_arg)
        return wasm_args

    def __call__(self, *py_args: Any) -> Any:
        wasm_args = self.from_py_args(py_args)
        res = self.ll.call(self.name, *wasm_args)
        w_type = self.w_functype.w_restype
        b = self.vm.builtins
        if w_type is b.w_void:
            assert res is None
            return None
        elif w_type is b.w_i32:
            return res
        elif w_type is b.w_bool:
            return bool(res)
        elif w_type is b.w_str:
            # res is a  spy_Str*
            addr = res
            length = self.ll.mem.read_i32(addr)
            utf8 = self.ll.mem.read(addr + 4, length)
            return utf8.decode('utf-8')
        else:
            assert False, f"Don't know how to read {w_type} from WASM"
