"""
PROTOTYPE: call prebuilt (compiled) stdlib functions from the interpreter.

See spy.build.native_stdlib for the build side, which also produces the
manifest: the list of functions and module-level variables which are
implemented by the compiled code.

The compiled code lives in the same WASM instance as the interpreter's heap
(vm.ll), so pointers can be passed around as plain addresses and module-level
variables can be shared by reading/writing the C globals in linear memory.
"""

from typing import TYPE_CHECKING, Any, Sequence

from spy.build import native_stdlib as ns
from spy.fqn import FQN
from spy.vm.b import TYPES, B
from spy.vm.cell import W_Cell
from spy.vm.function import W_ASTFunc, W_Func
from spy.vm.modules.unsafe.ptr import W_Ptr, W_PtrType
from spy.vm.object import W_Object
from spy.vm.str import W_Str
from spy.vm.primitive import W_F32, W_F64, W_I32, W_U32, W_Bool

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


def _to_wasm(w_arg: W_Object, vm: "SPyVM") -> Any:
    """
    wasm has only signed i32: u32 values >= 2**31 must be reinterpreted.
    """
    if isinstance(w_arg, W_Str):
        return w_arg.ptr
    v = vm.unwrap(w_arg)
    if isinstance(w_arg, W_U32) and v >= 2**31:
        v -= 2**32
    elif isinstance(w_arg, W_Bool):
        v = int(v)
    return v


def _from_wasm(vm: "SPyVM", w_T: Any, v: Any) -> W_Object:
    if w_T is B.w_u32:
        return W_U32(v & 0xFFFFFFFF)
    elif w_T is B.w_i32:
        return W_I32(v)
    elif w_T is B.w_f64:
        return W_F64(v)
    elif w_T is B.w_f32:
        return W_F32(v)
    elif w_T is B.w_bool:
        return vm.wrap(bool(v))
    elif w_T is B.w_str:
        return W_Str.from_ptr(vm, v)
    raise NotImplementedError(f"cannot marshal result of type {w_T}")


class W_NativeFunc(W_Func):
    """
    A function implemented by compiled code inside vm.ll.

    It takes the place of the W_ASTFunc with the same FQN, so it keeps its
    w_functype: the typechecker and opimpl machinery do not need to know.
    """

    def __init__(self, w_orig: W_ASTFunc, export_name: str) -> None:
        self.w_functype = w_orig.w_functype
        self.fqn = w_orig.fqn
        self.def_loc = w_orig.def_loc
        self.w_origin = w_orig.w_origin
        self.export_name = export_name
        self.w_orig = w_orig  # kept for debugging and fallback

    def __repr__(self) -> str:
        return f"<spy function '{self.fqn}' (native: {self.export_name})>"

    def raw_call(self, vm: "SPyVM", args_w: Sequence[W_Object]) -> W_Object:
        args = [_to_wasm(w_arg, vm) for w_arg in args_w]
        res = vm.ll.call(self.export_name, *args)
        w_restype = self.w_functype.w_restype
        if w_restype is TYPES.w_NoneType:
            return vm.wrap(None)
        return _from_wasm(vm, w_restype, res)


class W_NativeCell(W_Cell):
    """
    A module-level variable whose storage is a C global in linear memory.

    Two kinds are supported, the same as the ones supported by the C backend:

      - "i32": a 32-bit integer;
      - "ptr": {addr: i32, length: i32}, which matches the C struct in
        SPY_DEBUG builds.
    """

    def __init__(
        self, vm: "SPyVM", fqn: FQN, w_initial: W_Object, nc: ns.NativeCell
    ) -> None:
        self.fqn = fqn
        self._vm = vm
        self._kind = nc.kind
        self._w_T = vm.dynamic_type(w_initial)
        if nc.kind == "ptr":
            assert isinstance(self._w_T, W_PtrType)
        elif nc.kind == "i32":
            assert self._w_T is B.w_i32
        else:
            raise NotImplementedError(f"unsupported kind of native cell: {nc.kind}")
        self._addr = vm.ll.call(nc.export)
        # NOTE: the initial value is deliberately ignored: the C global is
        # statically initialized by the compiled module.

    def __repr__(self) -> str:
        return f"<spy native cell {self.fqn} @0x{self._addr:x}>"

    def get(self) -> W_Object:
        mem = self._vm.ll.mem
        if self._kind == "i32":
            return W_I32(mem.read_i32(self._addr))
        addr, length = mem.read_ptr(self._addr)
        return W_Ptr(self._w_T, addr, length)  # type: ignore

    def set(self, w_val: W_Object) -> None:
        mem = self._vm.ll.mem
        if self._kind == "i32":
            assert isinstance(w_val, W_I32)
            mem.write_i32(self._addr, int(w_val.value))
        else:
            assert isinstance(w_val, W_Ptr)
            mem.write_i32(self._addr, int(w_val.addr))
            mem.write_i32(self._addr + 4, int(w_val.length))


class NativeRegistry:
    """
    Which functions and variables are implemented by the compiled code, as
    described by the manifest.
    """

    funcs: dict[str, ns.NativeFunc]
    cells: dict[str, ns.NativeCell]

    def __init__(self, manifest: ns.Manifest) -> None:
        self.funcs = {f.fqn: f for f in manifest.funcs}
        self.cells = {c.fqn: c for c in manifest.cells}

    def maybe_replace_func(self, fqn: FQN, w_func: W_Object) -> W_Object:
        nf = self.funcs.get(str(fqn))
        if nf is None or not isinstance(w_func, W_ASTFunc):
            return w_func
        # the manifest is generated from the same sources, so the signature
        # must be the same: if not, something is out of sync, and calling the
        # compiled code would silently produce garbage
        w_ft = w_func.w_functype
        params = [ns.type_name(p.w_T) for p in w_ft.params]
        restype = ns.type_name(w_ft.w_restype)
        if (params, restype) != (nf.params, nf.restype):
            raise RuntimeError(
                f"native stdlib out of sync: {fqn} is ({', '.join(params)}) -> "
                f"{restype} but the manifest says ({', '.join(nf.params)}) -> "
                f"{nf.restype}"
            )
        return W_NativeFunc(w_func, nf.export)

    def maybe_make_cell(self, vm: "SPyVM", fqn: FQN, w_val: W_Object) -> W_Cell | None:
        nc = self.cells.get(str(fqn))
        if nc is None:
            return None
        return W_NativeCell(vm, fqn, w_val, nc)
