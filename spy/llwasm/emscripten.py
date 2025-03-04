"""
A pythonic way to instantiate Emscripten binaries.
"""

import sys
from typing import Any, Optional, Literal, Callable
from typing_extensions import Self
from asyncio import Future
import py.path
from .base import HostModule, LLWasmModuleBase, LLWasmInstanceBase, LLWasmMemoryBase, LLWasmType
from pyodide.ffi import run_sync, JsProxy
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

    def __init__(
            self,
            url: str,
            *,
            instance_factory: Optional[Callable] = None
    ) -> None:
        assert isinstance(url, str)
        self.url = url
        if instance_factory is None:
            # instance_factory the JS function which instantiates the
            # emscripten module
            self.instance_factory = run_sync(loadModule(url))
        else:
            self.instance_factory = instance_factory

    @classmethod
    async def async_new(cls, url: str) -> Self:
        assert isinstance(url, str)
        instance_factory = await loadModule(url)
        return cls(url, instance_factory=instance_factory)


class LLWasmInstance(LLWasmInstanceBase):
    def __init__(
            self,
            llmod: LLWasmModule,
            hostmods: list[HostModule] = [],
            *,
            instance: Optional[JsProxy] = None
    ) -> None:
        self.llmod = llmod

        if instance is None:
            self.instance = run_sync(self.link_and_instantiate(llmod, hostmods))
        else:
            self.instance = instance

        self.mem = LLWasmMemory(self.instance.HEAP8)
        for hostmod in hostmods:
            hostmod.ll = self

    @classmethod
    async def async_new(
            cls,
            llmod: LLWasmModule,
            hostmods: list[HostModule] = []
    ) -> Self:
        instance = await cls.link_and_instantiate(llmod, hostmods)
        return cls(llmod, hostmods, instance=instance)

    @staticmethod
    def link_and_instantiate(
            llmod: LLWasmModule,
            hostmods: list[HostModule]
    ) -> Future[Any]:
        """
        Return a PROMISE of the emscripten instance of the given module,
        linking all needed imports
        """
        def adjust_imports(imports: Any) -> None:
            from js import Object  # type: ignore
            env = imports.env
            for [name, val] in Object.entries(env):
                if not getattr(val, "stub", False):
                    continue
                for hostmod in hostmods:
                    if x := getattr(hostmod, "env_" + name, None):
                        setattr(env, name, x)
                        break
        return llmod.instance_factory(adjustWasmImports=adjust_imports)

    @classmethod
    def from_file(cls, f: py.path.local,
                  hostmods: list[HostModule]=[]) -> Self:
        llmod = LLWasmModule(str(f))
        return cls(llmod, hostmods)

    def get_export(self, name: str) -> Any:
        return getattr(self.instance, "_" + name)

    def get_addr_of_global(self, name: str) -> int:
        addr = self.get_export(name)
        assert isinstance(addr, int)
        return addr

    def call(self, name: str, *args: Any) -> Any:
        func = self.get_export(name)
        return func(*args)


class LLWasmMemory(LLWasmMemoryBase):

    def __init__(self, jsmem: Any) -> None:
        self.jsmem = jsmem

    def read(self, addr: int, n: int) -> bytearray:
        """
        Read n bytes of memory at the given address.
        """
        return self.jsmem.subarray(addr, addr+n).to_py()

    def write(self, addr: int, b: bytes) -> None:
        self.jsmem.subarray(addr, addr + len(b)).assign(b)
