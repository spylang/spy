from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import fixedint
import py.path
import wasmtime

from spy.fqn import FQN
from spy.libspy import LLSPyInstance
from spy.llwasm import LLWasmType
from spy.vm.b import TYPES, B
from spy.vm.bytes import ll_bytes_new
from spy.vm.cell import W_Cell
from spy.vm.function import W_ASTFunc, W_Func, W_FuncType
from spy.vm.modules.rawbuffer import RB
from spy.vm.modules.unsafe.ptr import W_PtrType
from spy.vm.object import W_Type
from spy.vm.str import ll_str_new
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


SCALAR_FROM_WASM: dict[W_Type, Callable[[Any], Any]] = {
    B.w_i8: fixedint.Int8,
    B.w_u8: fixedint.UInt8,
    B.w_i32: fixedint.Int32,
    B.w_u32: fixedint.UInt32,
    B.w_i64: fixedint.Int64,
    B.w_u64: fixedint.UInt64,
    B.w_bool: bool,
    B.w_f32: float,
    B.w_f64: float,
}


class WasmConverter:
    """
    Convert values between Python and WASM.

    On the WASM side, every value is represented as a *flat* sequence of
    scalars ("slots"). Most types take one slot, but some take more:

      - complex128: 2 slots (real, imag)
      - ptr[T]:     2 slots (addr, length), because we assume that libspy was
                    compiled with SPY_DEBUG
      - structs:    the concatenation of the slots of their fields.
    """

    vm: SPyVM
    ll: LLSPyInstance

    def __init__(self, vm: SPyVM, ll: LLSPyInstance) -> None:
        self.vm = vm
        self.ll = ll

    def to_wasm(self, w_T: W_Type, pyval: Any) -> list[Any]:
        """
        Convert a Python value into the flat list of WASM slots.
        """
        if w_T is TYPES.w_NoneType:
            return []  # None takes no slots
        elif w_T in (B.w_i32, B.w_u32, B.w_i8, B.w_u8, B.w_f64, B.w_bool):
            return [pyval]
        elif w_T in (B.w_i64, B.w_u64):
            return [int(pyval)]
        elif w_T is B.w_f32:
            return [float(pyval)]
        elif w_T is B.w_complex128:
            return [pyval.real, pyval.imag]
        elif w_T is B.w_str:
            # XXX: with the GC, we need to think how to keep this alive
            return [ll_str_new(self.ll, pyval)]
        elif w_T is B.w_bytes:
            # XXX: with the GC, we need to think how to keep this alive
            return [ll_bytes_new(self.ll, pyval)]
        elif isinstance(w_T, W_PtrType):
            assert isinstance(pyval, WasmPtr)
            return [pyval.addr, pyval.length]
        elif isinstance(w_T, W_StructType):
            if isinstance(pyval, slice):
                # convert slice into the equivalent UnwrappedStruct
                pyval = self.vm.unwrap(self.vm.wrap(pyval))
            assert isinstance(pyval, UnwrappedStruct)
            slots: list[Any] = []
            for w_field in w_T.iterfields_w():
                slots += self.to_wasm(w_field.w_T, pyval._content[w_field.name])
            return slots
        else:
            assert False, f"Unsupported type: {w_T}"

    def result_from_wasm(self, w_T: W_Type, res: Any) -> Any:
        """
        Convert the value returned by wasmtime into a Python value.

        wasmtime returns None for no values, a bare scalar for a single value
        and a list for multivalue: normalize everything into a list of slots.
        """
        if res is None:
            slots = []
        elif isinstance(res, (list, tuple)):
            slots = list(res)
        else:
            slots = [res]
        it = iter(slots)
        pyres = self.from_wasm(w_T, it)
        leftover = list(it)
        if leftover:
            raise ValueError(
                f"Wrong number of values for {w_T.fqn}: "
                f"expected {len(slots) - len(leftover)}, got {len(slots)}"
            )
        if isinstance(w_T, W_StructType):
            return self.struct_to_pyobject(w_T, pyres)
        return pyres

    def from_wasm(self, w_T: W_Type, it: Iterator[Any]) -> Any:
        """
        Read a value of type w_T, consuming the needed slots from `it`.
        """
        if w_T is TYPES.w_NoneType:
            return None
        elif w_T in SCALAR_FROM_WASM:
            return SCALAR_FROM_WASM[w_T](self._next(w_T, it))
        elif w_T is B.w_complex128:
            real = self._next(w_T, it)
            imag = self._next(w_T, it)
            return complex(real, imag)
        elif w_T is B.w_str:
            # str is a spy_StrObject*; read it from WASM memory
            _, _, utf8 = self.ll.read_str(self._next(w_T, it))
            return utf8.decode("utf-8")
        elif w_T is B.w_bytes:
            _, _, data = self.ll.read_bytes(self._next(w_T, it))
            return data
        elif w_T is RB.w_RawBuffer:
            # a spy_RawBuffer*. On wasm32, it looks like this:
            # struct {
            #     size_t length;
            #     /* 4 bytes of alignment */
            #     char buf[];
            # };
            addr = self._next(w_T, it)
            length = self.ll.mem.read_i32(addr)
            return self.ll.mem.read(addr + 8, length)
        elif isinstance(w_T, W_PtrType):
            addr = self._next(w_T, it)
            length = self._next(w_T, it)
            return WasmPtr(addr, length)
        elif isinstance(w_T, W_StructType):
            content = {
                w_field.name: self.from_wasm(w_field.w_T, it)
                for w_field in w_T.iterfields_w()
            }
            return UnwrappedStruct(w_T.fqn, content)
        else:
            assert False, f"Don't know how to read {w_T} from WASM"

    def _next(self, w_T: W_Type, it: Iterator[Any]) -> Any:
        try:
            return next(it)
        except StopIteration:
            raise ValueError(f"Not enough values to read {w_T.fqn} from WASM") from None

    def struct_to_pyobject(self, w_T: W_StructType, pyres: UnwrappedStruct) -> Any:
        if self.vm.is_tuple_type(w_T):
            return tuple(pyres._content.values())
        elif w_T.fqn == FQN("_list::list[i32]::_ListImpl"):
            return self._to_pylist_i32(pyres)
        elif w_T.fqn == FQN("_list::list[str]::_ListImpl"):
            return self._to_pylist_str(pyres)
        elif self.vm.is_list_type(w_T):
            raise NotImplementedError(f"Reading {w_T.fqn} out of WASM memory")
        elif w_T.fqn == FQN("_dict::dict[i32, i32]::_dict"):
            # we support only reading dict[i32, i32] for test
            return self._to_pydict_i32(pyres)
        else:
            return pyres

    def _to_pylist_i32(self, pyres: UnwrappedStruct) -> list[Any]:
        # struct ListData {
        #     i32 length;
        #     i32 capacity;
        #     ptr[i32] items;  // represented as {addr, length} in debug mode
        # }
        addr = self._ll_addr(pyres)
        length = self.ll.mem.read_i32(addr)
        items_addr = self.ll.mem.read_i32(addr + 8)
        return [self.ll.mem.read_i32(items_addr + i * 4) for i in range(length)]

    def _to_pylist_str(self, pyres: UnwrappedStruct) -> list[Any]:
        # struct ListData {
        #     i32 length;
        #     i32 capacity;
        #     ptr[StrObject] items;  // represented as {addr, length} in debug mode
        # }
        addr = self._ll_addr(pyres)
        length = self.ll.mem.read_i32(addr)
        items_addr = self.ll.mem.read_i32(addr + 8)
        result = []
        for i in range(length):
            str_addr = self.ll.mem.read_i32(items_addr + i * 4)
            _, _, utf8 = self.ll.read_str(str_addr)
            result.append(utf8.decode())
        return result

    def _to_pydict_i32(self, pyres: UnwrappedStruct) -> dict[Any, Any]:
        # struct DictData {
        #     ptr[i32] index;  // ptr is 8 bytes (4 for ptr + 4 for length)
        #     i32 log_size;
        #     i32 length;
        #     ptr[Entry] entries;
        # };
        #
        # struct Entry {
        #     i32 empty;
        #     i32 key;
        #     i32 value;
        # };
        addr = self._ll_addr(pyres)
        length = self.ll.mem.read_i32(addr + 12)
        entries = self.ll.mem.read_i32(addr + 16)
        entry_size = 12  # for dict[i32, i32]
        result = {}
        for i in range(1, length + 1):
            entry_addr = entries + i * entry_size
            empty = self.ll.mem.read_i32(entry_addr + 0)
            key = self.ll.mem.read_i32(entry_addr + 4)
            value = self.ll.mem.read_i32(entry_addr + 8)
            if not empty:
                result[key] = value
        return result

    @staticmethod
    def _ll_addr(pyres: UnwrappedStruct) -> int:
        """
        Address of the ListData/DictData pointed by the __ll__ field
        """
        ll_ptr = pyres._content["__ll__"]
        assert isinstance(ll_ptr, WasmPtr)
        return ll_ptr.addr


class WasmFuncWrapper:
    vm: SPyVM
    ll: LLSPyInstance
    c_name: str
    w_functype: W_FuncType
    conv: WasmConverter

    def __init__(
        self, vm: SPyVM, ll: LLSPyInstance, c_name: str, w_functype: W_FuncType
    ) -> None:
        self.vm = vm
        self.ll = ll
        self.c_name = c_name
        self.w_functype = w_functype
        self.conv = WasmConverter(vm, ll)

    def from_py_args(self, py_args: Any) -> list[Any]:
        a = len(py_args)
        b = self.w_functype.arity
        if a != b:
            raise TypeError(f"{self.c_name}: expected {b} arguments, got {a}")
        wasm_args: list[Any] = []
        for py_arg, param in zip(py_args, self.w_functype.params):
            wasm_args += self.conv.to_wasm(param.w_T, py_arg)
        return wasm_args

    def __call__(self, *py_args: Any, unwrap: bool = True) -> Any:
        assert unwrap, "unwrap=False is not supported by the C backend"
        wasm_args = self.from_py_args(py_args)
        res = self.ll.call(self.c_name, *wasm_args)
        return self.conv.result_from_wasm(self.w_functype.w_restype, res)
