from dataclasses import dataclass
from typing import Any

import py.path
import wasmtime

from spy.fqn import FQN
from spy.libspy import LLSPyInstance
from spy.llwasm import LLWasmType
from spy.vm.b import TYPES, B
from spy.vm.cell import W_Cell
from spy.vm.function import W_ASTFunc, W_Func, W_FuncType
from spy.vm.modules.rawbuffer import RB
from spy.vm.modules.unsafe.ptr import W_PtrType
from spy.vm.object import W_Type
from spy.vm.str import ll_spy_Str_new
from spy.vm.struct import UnwrappedStruct, W_StructType
from spy.vm.vm import SPyVM


@dataclass
class WasmPtr:
    addr: int
    length: int


class WasmModuleWrapper:
    vm: SPyVM
    modname: str
    ll: LLSPyInstance

    def __init__(self, vm: SPyVM, modname: str, f: py.path.local) -> None:
        self.vm = vm
        self.modname = modname
        self.w_mod = vm.modules_w[modname]
        self.ll = LLSPyInstance.from_file(f)

    def __repr__(self) -> str:
        return f"<WasmModuleWrapper '{self.ll.llmod}'>"

    def __getattr__(self, attr: str) -> Any:
        w_obj = self.w_mod.getattr(attr)
        if isinstance(w_obj, W_ASTFunc):
            if w_obj.color == "blue":
                raise NotImplementedError("cannot call a @blue func from a WASM module")
            return self.read_function(w_obj)

        elif isinstance(w_obj, W_Cell):
            return self.read_cell(w_obj)

        else:
            raise NotImplementedError(
                f"Don't know how to read this object from WASM: {w_obj}"
            )

    def read_function(self, w_func: W_Func) -> "WasmFuncWrapper":
        # sanity check
        wasm_func = self.ll.get_export(w_func.fqn.c_name)
        assert isinstance(wasm_func, wasmtime.Func)
        return WasmFuncWrapper(self.vm, self.ll, w_func.fqn.c_name, w_func.w_functype)

    def read_cell(self, w_cell: W_Cell) -> Any:
        wasm_glob = self.ll.get_export(w_cell.fqn.c_name)
        assert isinstance(wasm_glob, wasmtime.Global)
        w_T = self.vm.dynamic_type(w_cell.get())
        t: LLWasmType
        if w_T is B.w_i32:
            t = "int32_t"
        else:
            assert False, f"Unknown type: {w_T}"

        return self.ll.read_global(w_cell.fqn.c_name, deref=t)


class WasmFuncWrapper:
    vm: SPyVM
    ll: LLSPyInstance
    c_name: str
    w_functype: W_FuncType

    def __init__(
        self, vm: SPyVM, ll: LLSPyInstance, c_name: str, w_functype: W_FuncType
    ) -> None:
        self.vm = vm
        self.ll = ll
        self.c_name = c_name
        self.w_functype = w_functype

    def py2wasm(self, pyval: Any, w_T: W_Type) -> Any:
        if w_T in (B.w_i32, B.w_u32, B.w_i8, B.w_u8, B.w_f64, B.w_bool):
            return pyval
        elif w_T is B.w_str:
            # XXX: with the GC, we need to think how to keep this alive
            return ll_spy_Str_new(self.ll, pyval)
        elif isinstance(w_T, W_PtrType):
            assert isinstance(pyval, WasmPtr)
            return (pyval.addr, pyval.length)
        elif isinstance(w_T, W_StructType):
            # the function accepts a struct by value; wasmtime allows to pass
            # a flat sequence of fields. This is the opposite of what we do in
            # to_py_result. It works only for flat structs with simple types.
            assert isinstance(pyval, UnwrappedStruct)
            return tuple(pyval._content.values())
        else:
            assert False, f"Unsupported type: {w_T}"

    def from_py_args(self, py_args: Any) -> Any:
        a = len(py_args)
        b = self.w_functype.arity
        if a != b:
            raise TypeError(f"{self.c_name}: expected {b} arguments, got {a}")
        #
        wasm_args: list[Any] = []
        for py_arg, param in zip(py_args, self.w_functype.params):
            wasm_arg = self.py2wasm(py_arg, param.w_T)
            if type(wasm_arg) is tuple:
                # special case for multivalue
                wasm_args += wasm_arg
            else:
                wasm_args.append(wasm_arg)
        return wasm_args

    def to_py_result(self, w_T: W_Type, res: Any) -> Any:
        if w_T is TYPES.w_NoneType:
            assert res is None
            return None
        elif w_T in (B.w_i8, B.w_u8, B.w_i32, B.w_u32, B.w_f64):
            return res
        elif w_T is B.w_bool:
            return bool(res)
        elif w_T is B.w_str:
            # res is a  spy_Str*
            addr = res
            length = self.ll.mem.read_i32(addr)
            utf8 = self.ll.mem.read(addr + 4, length)
            return utf8.decode("utf-8")
        elif w_T is RB.w_RawBuffer:
            # res is a  spy_RawBuffer*
            # On wasm32, it looks like this:
            # struct {
            #     size_t length;
            #     /* 4 bytes of alignment */
            #     char buf[];
            # };
            addr = res
            length = self.ll.mem.read_i32(addr)
            buf = self.ll.mem.read(addr + 8, length)
            return buf
        elif isinstance(w_T, W_PtrType):
            # this assumes that we compiled libspy with SPY_DEBUG:
            #   - checked ptrs are represented as a struct { addr; length }
            #   - res contains a a list [addr, length] (because of WASM
            #     multivalue)
            addr, length = res
            return WasmPtr(addr, length)
        elif isinstance(w_T, W_StructType):
            # when you return struct-by-val from C, wasmtime automatically
            # converts them into a list, flattening nested structs
            assert isinstance(res, list)
            pyres = unflatten_struct(w_T, res)
            if w_T.fqn == FQN("_list::list[i32]::_ListImpl"):
                # we support only reading list[i32] for tests
                return self._to_pylist_i32(pyres)
            elif str(w_T.fqn).startswith("_list::list["):
                raise NotImplementedError(f"Reading {w_T.fqn} out of WASM memory")
            else:
                return pyres
        else:
            assert False, f"Don't know how to read {w_T} from WASM"

    def _to_pylist_i32(self, pyres: UnwrappedStruct) -> list[Any]:
        assert "__ll__" in pyres._content
        ll_ptr = pyres._content["__ll__"]
        assert isinstance(ll_ptr, WasmPtr)

        # Read ListData struct from memory
        # struct ListData {
        #     i32 length;
        #     i32 capacity;
        #     ptr[i32] items;  // represented as {addr, length} in debug mode
        # }
        addr = ll_ptr.addr
        length = self.ll.mem.read_i32(addr)
        capacity = self.ll.mem.read_i32(addr + 4)

        # Read the items pointer (starts at addr + 8)
        items_addr = self.ll.mem.read_i32(addr + 8)
        items_length = self.ll.mem.read_i32(addr + 12)

        # Read the actual i32 items
        result = []
        for i in range(length):
            item_addr = items_addr + i * 4
            item = self.ll.mem.read_i32(item_addr)
            result.append(item)

        return result

    def __call__(self, *py_args: Any, unwrap: bool = True) -> Any:
        assert unwrap, "unwrap=False is not supported by the C backend"
        wasm_args = self.from_py_args(py_args)
        res = self.ll.call(self.c_name, *wasm_args)
        w_T = self.w_functype.w_restype
        return self.to_py_result(w_T, res)


def unflatten_struct(w_T: W_StructType, flat_values: list[Any]) -> UnwrappedStruct:
    """
    Unflatten a struct from a flat list of values.

    When returning struct-by-val from C, wasmtime flattens nested structs
    into a single list. This function reconstructs the nested structure.
    """

    def unflatten(w_T: W_StructType, start_idx: int) -> tuple[UnwrappedStruct, int]:
        content: dict[str, Any] = {}
        idx = start_idx

        for w_field in w_T.iterfields_w():
            if isinstance(w_field.w_T, W_StructType):
                nested_result, idx = unflatten(w_field.w_T, idx)
                content[w_field.name] = nested_result
            elif isinstance(w_field.w_T, W_PtrType):
                # pointers are represented as {addr, length} in C/WASM
                if idx + 1 >= len(flat_values):
                    raise ValueError(
                        f"Not enough values to unflatten {w_T.fqn}: "
                        f"needed at least {idx + 2} for ptr field, got {len(flat_values)}"
                    )
                addr = flat_values[idx]
                length = flat_values[idx + 1]
                content[w_field.name] = WasmPtr(addr, length)
                idx += 2
            else:
                if idx >= len(flat_values):
                    raise ValueError(
                        f"Not enough values to unflatten {w_T.fqn}: "
                        f"needed at least {idx + 1}, got {len(flat_values)}"
                    )
                content[w_field.name] = flat_values[idx]
                idx += 1

        return UnwrappedStruct(w_T.fqn, content), idx

    result, consumed = unflatten(w_T, 0)
    if consumed != len(flat_values):
        raise ValueError(
            f"Wrong number of values for {w_T.fqn}: "
            f"expected {consumed}, got {len(flat_values)}"
        )
    return result
