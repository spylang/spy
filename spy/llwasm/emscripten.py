"""
A pythonic way to instantiate Emscripten binaries.
"""

from asyncio import Future
from pathlib import Path
from typing import Any, Callable, Optional

import py.path
from pyodide.code import run_js
from pyodide.ffi import JsException, JsProxy, create_once_callable, run_sync, to_js
from typing_extensions import Self

from .base import HostModule, LLWasmInstanceBase, LLWasmMemoryBase, LLWasmModuleBase

# xxx add way to catch only actual aborts
WasmTrap = JsException


loadModule = run_js("""
    const loadModule = async (f) => {
        const res = await import(f);
        return res.default;
    };
    loadModule
""")


def find_wasm_binary(mod_url: str) -> str:
    """
    Compute the URL of the .wasm, given the URL of the .mjs.

    This replicates Emscripten's findWasmBinary().
    """
    assert mod_url.endswith(".mjs"), f"unexpected module URL: {mod_url}"
    return mod_url[: -len(".mjs")] + ".wasm"


async def get_wasm_binary(url: str) -> Any:
    """
    Return the bytes of the wasm binary as a JS buffer.

    This replicates Emscripten's getWasmBinary().
    """
    if "://" in url and not url.startswith("file://"):
        from js import fetch  # type: ignore

        res = await fetch(url)
        return await res.arrayBuffer()
    else:
        f = py.path.local(url.removeprefix("file://"))
        return to_js(f.read_binary())


class LLWasmModule(LLWasmModuleBase):
    def __init__(
        self, url: str, *, instance_factory: Optional[Callable] = None
    ) -> None:
        assert isinstance(url, str)
        self.url = url
        if instance_factory is None:
            # instance_factory the JS function which instantiates the
            # emscripten module
            self.instance_factory = run_sync(loadModule(url))
        else:
            self.instance_factory = instance_factory

    def __repr__(self) -> str:
        return f"<LLWasmModule {self.url}>"

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
        instance: Optional[JsProxy] = None,
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
        cls, llmod: LLWasmModule, hostmods: list[HostModule] = []
    ) -> Self:
        instance = await cls.link_and_instantiate(llmod, hostmods)
        return cls(llmod, hostmods, instance=instance)

    @staticmethod
    def link_and_instantiate(
        llmod: LLWasmModule, hostmods: list[HostModule]
    ) -> Future[Any]:
        """
        Return a PROMISE of the emscripten instance of the given module,
        linking all needed imports
        """
        from js import Object, WebAssembly  # type: ignore
        from pyodide_js import FS

        def adjust_imports(imports: Any) -> None:
            env = imports.env
            for [name, val] in Object.entries(env):
                if not getattr(val, "stub", False):
                    continue
                for hostmod in hostmods:
                    if x := getattr(hostmod, "env_" + name, None):
                        setattr(env, name, x)
                        break

        @create_once_callable
        def connect_file_systems(module: Any) -> None:
            module.connectFileSystems(FS)

        return llmod.instance_factory(
            adjustImports=adjust_imports,
            preRun=[connect_file_systems],
            noInitialRun=True,
        )

    @classmethod
    def from_file(cls, f: py.path.local, hostmods: list[HostModule] = []) -> Self:
        llmod = LLWasmModule(str(f))
        return cls(llmod, hostmods)

    def get_export(self, name: str) -> Any:
        return getattr(self.instance, "_" + name)

    def all_exports(self) -> Any:
        return [x.removeprefix("_") for x in dir(self.instance) if x.startswith("_")]

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
        return self.jsmem.subarray(addr, addr + n).to_bytes()

    def write(self, addr: int, b: bytes) -> None:
        self.jsmem.subarray(addr, addr + len(b)).assign(b)
