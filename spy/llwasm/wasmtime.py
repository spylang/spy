"""
A pythonic wrapper around wasmtime.
"""

from typing import Any, Optional, Literal
from typing_extensions import Self
import py.path
import wasmtime as wt
import struct
from .base import HostModule, LLWasmModuleBase, LLWasmInstanceBase, LLWasmMemoryBase, LLWasmType

WasmTrap = wt.Trap

ENGINE = wt.Engine()

class LLWasmModule(LLWasmModuleBase):
    filename: str
    mod: wt.Module

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.mod = wt.Module.from_file(ENGINE, filename)

    def __repr__(self) -> str:
        return f'<LLWasmModule {self.filename}>'


def get_linker(
        store: wt.Store,
        llmod: LLWasmModule,
        *,
        wasi_config: Optional[wt.WasiConfig] = None,
        hostmods: Optional[list[HostModule]] = None,
    ) -> wt.Linker:
    """
    Setup a Linker which can be used to instantiate llmod.

    If wasi_config is supplied, the module will be linked agains WASI.

    The remaining non-wasi imports expected by llmod are searched inside the
    HostModules.
    """
    hostmods = hostmods or []
    def find_meth(imp: Any) -> Any:
        assert hostmods is not None
        methname = f'{imp.module}_{imp.name}'
        for hostmod in hostmods:
            meth = getattr(hostmod, methname, None)
            if meth is not None:
                return meth
        raise NotImplementedError(f'Missing WASM import: {methname}')

    py2w = {
        int: wt.ValType.i32(),
    }

    def FuncType_from_pyfunc(pyfunc: Any) -> wt.FuncType:
        annotations = pyfunc.__annotations__.copy()
        py_restype = annotations.pop('return')
        if py_restype is None:
            restypes = []
        else:
            restypes = [py2w[py_restype]]
        args = [py2w[pytype] for pytype in annotations.values()]
        return wt.FuncType(args, restypes)

    def get_wasmfunc(imp: Any) -> wt.Func:
        meth = find_meth(imp)
        functype = FuncType_from_pyfunc(meth)
        wasmfunc = wt.Func(store, functype, meth)
        return wasmfunc

    linker = wt.Linker(store.engine)
    if wasi_config:
        store.set_wasi(wasi_config)
        linker.define_wasi()

    for imp in llmod.mod.imports:
        if imp.module.startswith('wasi_'):
            continue
        func = get_wasmfunc(imp)
        linker.define(store, imp.module, imp.name, func)  # type: ignore

    return linker

def get_wasi_config() -> wt.WasiConfig:
    wasi_config = wt.WasiConfig()
    # eventually, we want to support argv, with either:
    #    wasi_config.argv = [...]
    #    wasi_config.inherit_argv()
    wasi_config.inherit_stdin()
    wasi_config.inherit_stdout()
    wasi_config.inherit_stderr()
    return wasi_config


class LLWasmInstance(LLWasmInstanceBase):
    f: py.path.local
    store: wt.Store
    instance: wt.Instance
    mem: 'LLWasmMemory'

    def __init__(self, llmod: LLWasmModule,
                 hostmods: list[HostModule]=[], *, instance=None) -> None:
        self.llmod = llmod
        self.store = wt.Store(ENGINE)
        linker = get_linker(
            self.store,
            self.llmod,
            wasi_config = get_wasi_config(),
            hostmods = hostmods
        )
        if instance is None:
            self.instance = linker.instantiate(self.store, self.llmod.mod)
        else:
            self.instance = instance
        memory = self.instance.exports(self.store).get('memory')
        assert isinstance(memory, wt.Memory)
        self.mem = LLWasmMemory(self.store, memory)
        for hostmod in hostmods:
            hostmod.ll = self


    @classmethod
    async def async_new(cls, llmod: LLWasmModule,
                        hostmods: list[HostModule]=[]) -> None:
        return cls(llmod, hostmods)

    @classmethod
    def from_file(cls, f: py.path.local,
                  hostmods: list[HostModule]=[]) -> Self:
        llmod = LLWasmModule(f)
        return cls(llmod, hostmods)

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


class LLWasmMemory(LLWasmMemoryBase):
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

    def write(self, addr: int, b: bytes) -> None:
        self.mem.write(self.store, b, addr)
