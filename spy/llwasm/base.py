LLWasmType = Literal[None, 'void *', 'int32_t', 'int16_t']

class LLWasmModuleBase:
    f: py.path.local

    def __repr__(self) -> str:
        return f'<LLWasmModule {self.f}>'

class LLWasmInstanceBase:
    def get_export(self, name: str) -> Any:
        raise NotImplementedError
    
    def all_exports(self) -> list[Any]:
        raise NotImplementedError
    
    @classmethod
    async def async_new(cls, llmod: LLWasmModule, hostmods: list[HostModule]=[]) -> None:
        raise NotImplementedError

    @classmethod
    def from_file(cls, f: py.path.local,
                  hostmods: list[HostModule]=[]) -> Self:
        raise NotImplementedError

    def call(self, name: str, *args: Any) -> Any:
        raise NotImplementedError

    def read_global(self, name: str, deref: LLWasmType = None) -> Any:
        r"""
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
        addr = self.get_export(name)
        if deref is None:
            return addr
        elif deref == 'int32_t' or deref == 'void *':
            return self.mem.read_i32(addr)
        elif deref == 'int16_t':
            return self.mem.read_i16(addr)
        else:
            assert False, f'Unknown type: {deref}'


class HostModule:
    """
    Base class for host modules.

    Each host module can provide one or more WASM import, used by link().
    """
    ll: 'LLWasmInstanceBase' # this attribute is set by LLWasmInstance.__init__


class LLWasmMemoryBase:
    def read_i32(self, addr: int) -> int:
        rawbytes = self.read(addr, 4)
        return struct.unpack('i', rawbytes)[0]

    def read_i16(self, addr: int) -> int:
        rawbytes = self.read(addr, 2)
        return struct.unpack('h', rawbytes)[0]

    def read_i8(self, addr: int) -> int:
        rawbytes = self.read(addr, 1)
        return rawbytes[0]

    def read_f64(self, addr: int) -> int:
        rawbytes = self.read(addr, 8)
        return struct.unpack('d', rawbytes)[0]

    def read_ptr(self, addr: int) -> tuple[int, int]:
        """
        Read a ptr, which we represent as a struct {addr; length }
        """
        v_addr = self.read_i32(addr)
        v_length = self.read_i32(addr+4)
        return v_addr, v_length

    def read_cstr(self, addr: int) -> bytearray:
        """
        Read the NULL-terminated string starting at addr.

        WARNING: this is inefficient because it creates a temporary bytearray
        for every char To be faster we probably need to bypass wasmtime and
        access directly the ctypes-based view of the memory.
        """
        n = 0
        while self.read_i8(addr + n) != 0:
            n += 1
        return self.read(addr, n)

    def write_i32(self, addr: int, v: int) -> None:
        self.write(addr, struct.pack('i', v))

    def write_i16(self, addr: int, v: int) -> None:
        self.write(addr, struct.pack('h', v))

    def write_i8(self, addr: int, v: int) -> None:
        self.write(addr, struct.pack('b', v))

    def write_f64(self, addr: int, v: float) -> None:
        self.write(addr, struct.pack('d', v))

    def write_ptr(self, addr: int, v_addr: int, v_length: int) -> None:
        """
        Write a ptr { addr; length } to the given addr
        """
        self.write_i32(addr, v_addr)
        self.write_i32(addr+4, v_length)
