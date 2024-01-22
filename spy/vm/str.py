from typing import TYPE_CHECKING, Any
from spy.llwasm import LLWasmInstance
from spy.vm.object import W_Object, spytype
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

def ll_spy_Str_new(ll: LLWasmInstance, s: str) -> int:
    """
    Create a new spy_Str object inside the given LLWasmInstance, and fill it
    with the utf8-encoded content of s.

    Return the corresponding 'spy_Str *'
    """
    utf8 = s.encode('utf-8')
    length = len(utf8)
    ptr = ll.call('spy_str_alloc', length)
    ll.mem.write(ptr+4, utf8)
    return ptr

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

    def __init__(self, vm: 'SPyVM', s: str) -> None:
        ptr = ll_spy_Str_new(vm.ll, s)
        self.vm = vm
        self.ptr = ptr

    @staticmethod
    def from_ptr(vm: 'SPyVM', ptr: int) -> 'W_str':
        w_res = W_str.__new__(W_str)
        w_res.vm = vm
        w_res.ptr = ptr
        return w_res

    def get_length(self) -> int:
        return self.vm.ll.mem.read_i32(self.ptr)

    def get_utf8(self) -> bytes:
        length = self.get_length()
        ba = self.vm.ll.mem.read(self.ptr+4, length)
        return bytes(ba)

    def _as_str(self) -> str:
        return self.get_utf8().decode('utf-8')

    def __repr__(self) -> str:
        s = self._as_str()
        return f'W_str({s!r})'

    def spy_unwrap(self, vm: 'SPyVM') -> str:
        return self._as_str()
