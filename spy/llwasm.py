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
import py.path
import wasmtime as wt
import struct

LLWasmType = Literal[None, 'void *', 'int32_t', 'int16_t']
ENGINE = wt.Engine()

def FuncType_from_pyfunc(pyfunc: Any) -> wt.FuncType:
    py2w = {
        int: wt.ValType.i32(),
    }
    annotations = pyfunc.__annotations__.copy()
    #
    py_restype = annotations.pop('return')
    if py_restype is None:
        restypes = []
    else:
        restypes = [py2w[py_restype]]
    #
    args = [py2w[pytype] for pytype in annotations.values()]
    return wt.FuncType(args, restypes)

class LLWasmModule:
    f: py.path.local
    mod: wt.Module

    def __init__(self, f: py.path.local) -> None:
        self.f = f
        self.mod = wt.Module.from_file(ENGINE, str(f))

    def __repr__(self) -> str:
        return '<LLWasmModule {self.f}>'

class LLWasmInstance:
    f: py.path.local
    store: wt.Store
    instance: wt.Instance
    mem: 'LLWasmMemory'

    def __init__(self, llmod: LLWasmModule) -> None:
        self.llmod = llmod
        self.store = wt.Store(ENGINE)
        imports = self.resolve_imports()
        self.instance = wt.Instance(self.store, self.llmod.mod, imports)
        memory = self.instance.exports(self.store).get('memory')
        assert isinstance(memory, wt.Memory)
        self.mem = LLWasmMemory(self.store, memory)

    @classmethod
    def from_file(cls, f: py.path.local) -> 'LLWasmInstance':
        llmod = LLWasmModule(f)
        return cls(llmod)

    def resolve_imports(self) -> Any:
        imports = []
        for imp in self.llmod.mod.imports:
            methname = f'{imp.module}_{imp.name}'
            meth = getattr(self, methname, None)
            if meth is None:
                raise NotImplementedError(f'Missing WASM import: {methname}')
            functype = FuncType_from_pyfunc(meth)
            wasmfunc = wt.Func(self.store, functype, meth)
            imports.append(wasmfunc)
        return imports

    def get_export(self, name: str) -> Any:
        exports = self.instance.exports(self.store)
        wasm_obj = exports.get(name)
        if wasm_obj is None:
            raise AttributeError(name)
        return wasm_obj

    def all_exports(self) -> Any:
        exports = self.instance.exports(self.store)
        return list(exports._extern_map)

    def call(self, name: str, *args: Any) -> Any:
        func = self.get_export(name)
        assert isinstance(func, wt.Func)
        return func(self.store, *args)

    def read_global(self, name: str, deref: LLWasmType = None) -> Any:
        """
        Read the given global.

        The semantics is a bit unfortunately: currently, clang always store C
        globals in linear memory, meaning that the corresponding WASM global
        contains a *pointer* to the memory.

        clang has plans to support "real" WASM globals: see
        https://github.com/emscripten-core/emscripten/issues/12793

        If we are reading a scalar, we most likely want to deref the pointer
        and cast the bytes to the desired type. However, in some cases we are
        interested in the address, e.g. if the global points to an array or a
        struct: in that case, we can pass deref=None.

        For example, the following C program:
            int16_t a = 0xAAAA;
            int16_t b[] = {0xBBBB, 0xCCCC};

        Produces the following WASM:
            (global $a i32 (i32.const 1024))
            (global $b i32 (i32.const 1026))
            (data $d0 (i32.const 1024) "\aa\aa\bb\bb\cc\cc")

        In this case:
            read_global('a', deref=None) == 1024
            read_global('b', deref=None) == 1026
            read_global('a', deref='i16') == 0xAAAA
            read_global('b', deref='i16') == 0xBBBB # first item of the array
        """
        g = self.get_export(name)
        assert isinstance(g, wt.Global)
        addr = g.value(self.store)
        assert isinstance(addr, int)
        if deref is None:
            return addr
        elif deref == 'int32_t' or deref == 'void *':
            return self.mem.read_i32(addr)
        elif deref == 'int16_t':
            return self.mem.read_i16(addr)
        else:
            assert False, f'Unknown type: {deref}'


class LLWasmMemory:
    """
    Thin wrapper around wt.Memory
    """
    store: wt.Store
    mem: wt.Memory

    def __init__(self, store: wt.Store, mem: wt.Memory):
        self.store = store
        self.mem = mem

    def read(self, addr: int, n: int) -> bytearray:
        """
        Read n bytes of memory at the given address.
        """
        return self.mem.read(self.store, addr, addr+n)

    def read_i32(self, addr: int) -> int:
        rawbytes = self.read(addr, 4)
        return struct.unpack('i', rawbytes)[0]

    def read_i16(self, addr: int) -> int:
        rawbytes = self.read(addr, 2)
        return struct.unpack('h', rawbytes)[0]

    def write(self, addr: int, b: bytes) -> None:
        self.mem.write(self.store, b, addr)
