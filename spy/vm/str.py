from typing import TYPE_CHECKING, Any
from spy.vm.object import W_Object, spytype
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM



@spytype('str')
class W_str(W_Object):
    """
    An unicode string, internally represented as UTF-8.

    This is basically a 'spy_Str *', i.e. a pointer to a C struct which
    resides in the linear memory of the VM:
        typedef struct {
            size_t length;
            const char utf8[];
        } spy_Str;
    """
    vm: 'SPyVM'
    ptr: int

    def __init__(self, vm: 'SPyVM', ptr: int) -> None:
        self.vm = vm
        self.ptr = ptr

    @staticmethod
    def from_str(vm: 'SPyVM', s: str) -> 'W_str':
        utf8 = s.encode('utf-8')
        length = len(utf8)
        p = vm.llmod.call('spy_StrAlloc', length)
        vm.llmod.write_mem(p+4, utf8)
        return W_str(vm, p)

    def get_length(self) -> int:
        return self.vm.llmod.read_mem_i32(self.ptr)

    def get_utf8(self) -> bytes:
        length = self.get_length()
        ba = self.vm.llmod.read_mem(self.ptr+4, length)
        return bytes(ba)

    def _as_str(self) -> str:
        return self.get_utf8().decode('utf-8')

    def __repr__(self) -> str:
        s = self._as_str()
        return f'W_str({s!r})'

    def spy_unwrap(self, vm: 'SPyVM') -> str:
        return self._as_str()
