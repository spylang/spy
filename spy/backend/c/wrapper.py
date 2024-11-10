import struct
from typing import Any, Optional
import py.path
import wasmtime
from spy.fqn import FQN
from spy.llwasm import LLWasmType
from spy.libspy import LLSPyInstance
from spy.vm.object import W_Type
from spy.vm.str import ll_spy_Str_new
from spy.vm.module import W_Module
from spy.vm.function import W_Func, W_FuncType
from spy.vm.vm import SPyVM
from spy.vm.b import B
from spy.vm.modules.rawbuffer import RB
from spy.vm.modules.types import W_TypeDef

class WasmModuleWrapper:
    vm: SPyVM
    modname: str
    ll: LLSPyInstance

    def __init__(self, vm: SPyVM, modname: str, f: py.path.local) -> None:
        self.vm = vm
        self.modname = modname
        self.ll = LLSPyInstance.from_file(f)

    def __repr__(self) -> str:
        return f"<WasmModuleWrapper '{self.ll.llmod.f}'>"

    def __getattr__(self, attr: str) -> Any:
        fqn = FQN([self.modname, attr])
        wasm_obj = self.ll.get_export(fqn.c_name)
        if isinstance(wasm_obj, wasmtime.Func):
            return self.read_function(fqn)
        elif isinstance(wasm_obj, wasmtime.Global):
            return self.read_global(fqn)
        else:
            t = type(wasm_obj)
            raise NotImplementedError(f'Unknown WASM object: {t}')

    def read_function(self, fqn: FQN) -> 'WasmFuncWrapper':
        w_func = self.vm.lookup_global(fqn)
        assert isinstance(w_func, W_Func)
        return WasmFuncWrapper(self.vm, self.ll,
                               fqn.c_name, w_func.w_functype)

    def read_global(self, fqn: FQN) -> Any:
        w_val = self.vm.lookup_global(fqn)
        assert w_val is not None
        w_type = self.vm.dynamic_type(w_val)
        t: LLWasmType
        if w_type is B.w_i32:
            t = 'int32_t'
        else:
            assert False, f'Unknown type: {w_type}'

        return self.ll.read_global(fqn.c_name, deref=t)


class WasmFuncWrapper:
    vm: SPyVM
    ll: LLSPyInstance
    c_name: str
    w_functype: W_FuncType

    def __init__(self, vm: SPyVM, ll: LLSPyInstance, c_name: str,
                 w_functype: W_FuncType) -> None:
        self.vm = vm
        self.ll = ll
        self.c_name = c_name
        self.w_functype = w_functype

    def py2wasm(self, pyval: Any, w_type: W_Type) -> Any:
        if w_type in (B.w_i32, B.w_f64):
            return pyval
        elif w_type is B.w_str:
            # XXX: with the GC, we need to think how to keep this alive
            return ll_spy_Str_new(self.ll, pyval)
        else:
            assert False, f'Unsupported type: {w_type}'

    def from_py_args(self, py_args: Any) -> Any:
        a = len(py_args)
        b = self.w_functype.arity
        if a != b:
            raise TypeError(f'{self.c_name}: expected {b} arguments, got {a}')
        #
        wasm_args = []
        for py_arg, param in zip(py_args, self.w_functype.params):
            wasm_arg = self.py2wasm(py_arg, param.w_type)
            wasm_args.append(wasm_arg)
        return wasm_args

    def __call__(self, *py_args: Any) -> Any:
        wasm_args = self.from_py_args(py_args)
        res = self.ll.call(self.c_name, *wasm_args)
        w_type = self.w_functype.w_restype
        if isinstance(w_type, W_TypeDef):
            w_type = w_type.w_origintype
        #
        if w_type is B.w_void:
            assert res is None
            return None
        elif w_type is B.w_i32:
            return res
        elif w_type is B.w_f64:
            return res
        elif w_type is B.w_bool:
            return bool(res)
        elif w_type is B.w_str:
            # res is a  spy_Str*
            addr = res
            length = self.ll.mem.read_i32(addr)
            utf8 = self.ll.mem.read(addr + 4, length)
            return utf8.decode('utf-8')
        elif w_type is RB.w_RawBuffer:
            # res is a  spy_RawBuffer*
            addr = res
            length = self.ll.mem.read_i32(addr)
            buf = self.ll.mem.read(addr + 4, length)
            return buf
        else:
            assert False, f"Don't know how to read {w_type} from WASM"
