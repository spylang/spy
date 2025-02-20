"""
A pythonic way to instantiate Emscripten binaries.
"""

import sys
from typing import Any, Optional, Literal
from typing_extensions import Self
from asyncio import Future
import py.path
from .base import HostModule, LLWasmModuleBase, LLWasmInstanceBase, LLWasmMemoryBase, LLWasmType

from pyodide.ffi import run_sync
from pyodide.code import run_js
loadModule = run_js("""
    const loadModule = async (f) => {
        const res = await import(f.replace("/spy", "."));
        return res.default;
    };
    loadModule
""")

class LLWasmModule(LLWasmModuleBase):
    f: py.path.local

    def __init__(self, f: py.path.local, *, make_instance=None) -> None:
        self.f = f
        if make_instance is None:
            # JS function that when called makes an instance of the emscripten module
            self.make_instance = run_sync(loadModule(str(f.new(ext=".mjs"))))
        else:
            self.make_instance = make_instance

    @classmethod
    async def async_new(cls, f: py.path.local):
        make_instance = await loadModule(str(f.new(ext=".mjs")))
        return cls(f, make_instance=make_instance)


class LLWasmInstance(LLWasmInstanceBase):
    def __init__(self, llmod: LLWasmModule,
                 hostmods: list[HostModule]=[], *, instance=None) -> None:
        self.llmod = llmod

        if instance is None:
            self.instance = run_sync(self._make_instance_promise(llmod, hostmods))
        else:
            self.instance = instance

        self.mem = LLWasmMemoryPyodide(self.instance.HEAP8)
        for hostmod in hostmods:
            hostmod.ll = self

    @classmethod
    async def async_new(cls, llmod: LLWasmModule, hostmods: list[HostModule]=[]) -> None:
        return cls(llmod, hostmods, instance=await cls._make_instance_promise(llmod, hostmods))

    @staticmethod
    def _make_instance_promise(llmod: LLWasmModule, hostmods: list[HostModule]) -> Future[Any]:
        def adjust_imports(imports):
            from js import Object
            env = imports.env
            for [name, val] in Object.entries(env):
                if not val.stub:
                    continue
                for hostmod in hostmods:
                    if x := getattr(hostmod, "env_" + name, None):
                        setattr(env, name, x)
                        break
        return llmod.make_instance(adjustWasmImports=adjust_imports)

    @classmethod
    def from_file(cls, f: py.path.local,
                  hostmods: list[HostModule]=[]) -> Self:
        llmod = LLWasmModule(f)
        return cls(llmod, hostmods)

    def get_export(self, name: str) -> Any:
        return getattr(self.instance, "_" + name)

    def call(self, name: str, *args: Any) -> Any:
        func = self.get_export(name)
        return func(*args)


class LLWasmMemory(LLWasmMemoryBase):
    def __init__(self, jsmem):
        self.jsmem = jsmem

    def read(self, addr: int, n: int) -> bytearray:
        """
        Read n bytes of memory at the given address.
        """
        return self.jsmem.subarray(addr, addr+n).to_py()

    def write(self, addr: int, b: bytes) -> None:
        self.jsmem.subarray(addr, addr + len(b)).assign(b)
