"""
A pythonic wrapper around wasmtime.

It is called 'LL' for two reasons:

  - it exposes a low-level view on the code, compared to other wrappers which
    are more higher level (e.g., the concept of strings doesn't exist, we only
    have ints, floats and bytes of memory).

  - it's an unused prefix: other prefixes as "Py", "Wasm", "W" etc. would have
    been very confusing :)
"""

from typing import Any, Optional, Literal
from typing_extensions import Self
import py.path
# import wasmtime as wt
import struct
from js_loader import loadModule
from asyncio import get_event_loop

LLWasmType = Literal[None, 'void *', 'int32_t', 'int16_t']
# ENGINE = wt.Engine()

class LLWasmModule:
    f: py.path.local
    # mod: wt.Module

    def __init__(self, f: py.path.local) -> None:
        self.f = f
        self.mod = get_event_loop().run_until_complete(loadModule(str(f.new(ext=".mjs"))))


#     def __repr__(self) -> str:
#         return f'<LLWasmModule {self.f}>'


class HostModule:
    """
    Base class for host modules.

    Each host module can provide one or more WASM import, used by link().
    """
    ll: 'LLWasmInstance' # this attribute is set by LLWasmInstance.__init__


# def get_linker(
#         store: wt.Store,
#         llmod: LLWasmModule,
#         *,
#         wasi_config: Optional[wt.WasiConfig] = None,
#         hostmods: Optional[list[HostModule]] = None,
#     ) -> wt.Linker:
#     """
#     Setup a Linker which can be used to instantiate llmod.

#     If wasi_config is supplied, the module will be linked agains WASI.

#     The remaining non-wasi imports expected by llmod are searched inside the
#     HostModules.
#     """
#     hostmods = hostmods or []
#     def find_meth(imp: Any) -> Any:
#         assert hostmods is not None
#         methname = f'{imp.module}_{imp.name}'
#         for hostmod in hostmods:
#             meth = getattr(hostmod, methname, None)
#             if meth is not None:
#                 return meth
#         raise NotImplementedError(f'Missing WASM import: {methname}')

#     py2w = {
#         int: wt.ValType.i32(),
#     }

#     def FuncType_from_pyfunc(pyfunc: Any) -> wt.FuncType:
#         annotations = pyfunc.__annotations__.copy()
#         py_restype = annotations.pop('return')
#         if py_restype is None:
#             restypes = []
#         else:
#             restypes = [py2w[py_restype]]
#         args = [py2w[pytype] for pytype in annotations.values()]
#         return wt.FuncType(args, restypes)

#     def get_wasmfunc(imp: Any) -> wt.Func:
#         meth = find_meth(imp)
#         functype = FuncType_from_pyfunc(meth)
#         wasmfunc = wt.Func(store, functype, meth)
#         return wasmfunc

#     linker = wt.Linker(store.engine)
#     if wasi_config:
#         store.set_wasi(wasi_config)
#         linker.define_wasi()

#     for imp in llmod.mod.imports:
#         if imp.module.startswith('wasi_'):
#             continue
#         func = get_wasmfunc(imp)
#         linker.define(store, imp.module, imp.name, func)  # type: ignore

#     return linker

# def get_wasi_config() -> wt.WasiConfig:
#     wasi_config = wt.WasiConfig()
#     # eventually, we want to support argv, with either:
#     #    wasi_config.argv = [...]
#     #    wasi_config.inherit_argv()
#     wasi_config.inherit_stdin()
#     wasi_config.inherit_stdout()
#     wasi_config.inherit_stderr()
#     return wasi_config


class LLWasmInstance:
#     store: wt.Store
#     instance: wt.Instance
#     mem: 'LLWasmMemory'

    def __init__(self, llmod: LLWasmModule,
                 hostmods: list[HostModule]=[]) -> None:
        self.instance = llmod
#         self.store = wt.Store(ENGINE)
#         linker = get_linker(
#             self.store,
#             self.llmod,
#             wasi_config = get_wasi_config(),
#             hostmods = hostmods
#         )
#         self.instance = linker.instantiate(self.store, self.llmod.mod)
#         memory = self.instance.exports(self.store).get('memory')
#         assert isinstance(memory, wt.Memory)
#         self.mem = LLWasmMemory(self.store, memory)
#         for hostmod in hostmods:
#             hostmod.ll = self

    @classmethod
    def from_file(cls, f: py.path.local,
                  hostmods: list[HostModule]=[]) -> Self:
        llmod = LLWasmModule(f)
        return cls(llmod, hostmods)

    def get_export(self, name: str) -> Any:
        return getattr(self.instance.mod, "_" + name)

    def all_exports(self) -> Any:
        exports = self.instance.exports(self.store)
        return list(exports._extern_map)

    def call(self, name: str, *args: Any) -> Any:
        func = self.get_export(name)
        return func(*args)

#     def read_global(self, name: str, deref: LLWasmType = None) -> Any:
#         r"""
#         Read the given global.

#         The semantics is a bit unfortunately: currently, clang always store C
#         globals in linear memory, meaning that the corresponding WASM global
#         contains a *pointer* to the memory.

#         clang has plans to support "real" WASM globals: see
#         https://github.com/emscripten-core/emscripten/issues/12793

#         If we are reading a scalar, we most likely want to deref the pointer
#         and cast the bytes to the desired type. However, in some cases we are
#         interested in the address, e.g. if the global points to an array or a
#         struct: in that case, we can pass deref=None.

#         For example, the following C program:
#             int16_t a = 0xAAAA;
#             int16_t b[] = {0xBBBB, 0xCCCC};

#         Produces the following WASM:
#             (global $a i32 (i32.const 1024))
#             (global $b i32 (i32.const 1026))
#             (data $d0 (i32.const 1024) "\aa\aa\bb\bb\cc\cc")

#         In this case:
#             read_global('a', deref=None) == 1024
#             read_global('b', deref=None) == 1026
#             read_global('a', deref='i16') == 0xAAAA
#             read_global('b', deref='i16') == 0xBBBB # first item of the array
#         """
#         g = self.get_export(name)
#         assert isinstance(g, wt.Global)
#         addr = g.value(self.store)
#         assert isinstance(addr, int)
#         if deref is None:
#             return addr
#         elif deref == 'int32_t' or deref == 'void *':
#             return self.mem.read_i32(addr)
#         elif deref == 'int16_t':
#             return self.mem.read_i16(addr)
#         else:
#             assert False, f'Unknown type: {deref}'


class LLWasmMemory:
    pass
#     """
#     Thin wrapper around wt.Memory
#     """
#     store: wt.Store
#     mem: wt.Memory

#     def __init__(self, store: wt.Store, mem: wt.Memory):
#         self.store = store
#         self.mem = mem

#     def read(self, addr: int, n: int) -> bytearray:
#         """
#         Read n bytes of memory at the given address.
#         """
#         return self.mem.read(self.store, addr, addr+n)

#     def read_i32(self, addr: int) -> int:
#         rawbytes = self.read(addr, 4)
#         return struct.unpack('i', rawbytes)[0]

#     def read_i16(self, addr: int) -> int:
#         rawbytes = self.read(addr, 2)
#         return struct.unpack('h', rawbytes)[0]

#     def read_i8(self, addr: int) -> int:
#         rawbytes = self.read(addr, 1)
#         return rawbytes[0]

#     def read_f64(self, addr: int) -> int:
#         rawbytes = self.read(addr, 8)
#         return struct.unpack('d', rawbytes)[0]

#     def read_ptr(self, addr: int) -> tuple[int, int]:
#         """
#         Read a ptr, which we represent as a struct {addr; length }
#         """
#         v_addr = self.read_i32(addr)
#         v_length = self.read_i32(addr+4)
#         return v_addr, v_length

#     def read_cstr(self, addr: int) -> bytearray:
#         """
#         Read the NULL-terminated string starting at addr.

#         WARNING: this is inefficient because it creates a temporary bytearray
#         for every char To be faster we probably need to bypass wasmtime and
#         access directly the ctypes-based view of the memory.
#         """
#         n = 0
#         while self.read_i8(addr + n) != 0:
#             n += 1
#         return self.read(addr, n)

#     def write(self, addr: int, b: bytes) -> None:
#         self.mem.write(self.store, b, addr)

#     def write_i32(self, addr: int, v: int) -> None:
#         self.write(addr, struct.pack('i', v))

#     def write_i16(self, addr: int, v: int) -> None:
#         self.write(addr, struct.pack('h', v))

#     def write_i8(self, addr: int, v: int) -> None:
#         self.write(addr, struct.pack('b', v))

#     def write_f64(self, addr: int, v: float) -> None:
#         self.write(addr, struct.pack('d', v))

#     def write_ptr(self, addr: int, v_addr: int, v_length: int) -> None:
#         """
#         Write a ptr { addr; length } to the given addr
#         """
#         self.write_i32(addr, v_addr)
#         self.write_i32(addr+4, v_length)
