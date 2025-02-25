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

class WasmTrap(Exception):
    # xxx add way to catch only actual aborts
    pass



loadModule = run_js("""
    const loadModule = async (f) => {
        const res = await import(f);
        return res.default;
    };
    loadModule
""")

class LLWasmModule(LLWasmModuleBase):

    def __init__(self, url: str, *, make_instance=None) -> None:
        assert isinstance(url, str)
        self.url = url
        if make_instance is None:
            # JS function that when called makes an instance of the emscripten
            # module
            #self.make_instance = run_sync(loadModule(str(f.new(ext=".mjs"))))
            self.make_instance = run_sync(loadModule(url))
        else:
            self.make_instance = make_instance

    @classmethod
    async def async_new(cls, url: str):
        assert isinstance(url, str)
        make_instance = await loadModule(url)
        return cls(f, make_instance=make_instance)


class LLWasmInstance(LLWasmInstanceBase):
    def __init__(self, llmod: LLWasmModule,
                 hostmods: list[HostModule]=[], *, instance=None) -> None:
        self.llmod = llmod

        if instance is None:
            self.instance = run_sync(self._make_instance_promise(llmod, hostmods))
        else:
            self.instance = instance

        self.mem = LLWasmMemory(self.instance.HEAP8)
        for hostmod in hostmods:
            hostmod.ll = self

    @classmethod
    async def async_new(cls, llmod: LLWasmModule, hostmods: list[HostModule]=[]) -> None:
        instance = await cls._make_instance_promise(llmod, hostmods)
        return cls(llmod, hostmods, instance=instance)

    @staticmethod
    def _make_instance_promise(llmod: LLWasmModule, hostmods: list[HostModule]) -> Future[Any]:
        def adjust_imports(imports):
            from js import Object
            env = imports.env
            for [name, val] in Object.entries(env):
                if not getattr(val, "stub", False):
                    continue
                for hostmod in hostmods:
                    if x := getattr(hostmod, "env_" + name, None):
                        setattr(env, name, x)
                        break

        return llmod.make_instance(adjustWasmImports=adjust_imports)

    @classmethod
    def from_file(cls, f: py.path.local,
                  hostmods: list[HostModule]=[]) -> Self:
        llmod = LLWasmModule(str(f))
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
