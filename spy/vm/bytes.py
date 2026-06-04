from typing import TYPE_CHECKING

from spy.libspy import LLSPyInstance
from spy.vm.b import BUILTINS, B
from spy.vm.builtin import builtin_method
from spy.vm.object import W_Object
from spy.vm.primitive import W_I32
from spy.vm.str import W_Str

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


def ll_bytes_new(ll: LLSPyInstance, b: bytes) -> int:
    """
    Create a new spy_BytesObject inside the given LLSPyInstance, filling it
    with the content of b.

    Returns the corresponding 'spy_BytesObject *'
    """
    length = len(b)
    ptr = ll.call("spy_bytes_alloc", length)
    data_ptr = ll.mem.read_i32(ptr + ll.bytes_layout.data_offset)
    ll.mem.write(data_ptr, b)
    return ptr


@B.builtin_type("bytes", lazy_definition=True)
class W_Bytes(W_Object):
    """
    A sequence of bytes.

    This is basically a 'spy_BytesObject *', i.e. a pointer to a C struct
    which resides in the linear memory of the VM:
        typedef struct {
            size_t length;
            int32_t hash;
            uint8_t *data;
        } spy_BytesObject;
    """

    __spy_storage_category__ = "value"
    __spy_lazy_attributes__ = {}

    vm: "SPyVM"
    ptr: int

    def __init__(self, vm: "SPyVM", b: bytes) -> None:
        self.vm = vm
        self.ptr = ll_bytes_new(vm.ll, b)

    @staticmethod
    def from_ptr(vm: "SPyVM", ptr: int) -> "W_Bytes":
        w_res = W_Bytes.__new__(W_Bytes)
        w_res.vm = vm
        w_res.ptr = ptr
        return w_res

    def get_length(self) -> int:
        ll = self.vm.ll
        return ll.mem.read_i32(self.ptr + ll.bytes_layout.length_offset)

    def get_data(self) -> bytes:
        _, _, data = self.vm.ll.read_bytes(self.ptr)
        return data

    def __repr__(self) -> str:
        b = self.get_data()
        return f"W_Bytes({b!r})"

    def spy_unwrap(self, vm: "SPyVM") -> bytes:
        return self.get_data()

    def spy_key(self, vm: "SPyVM") -> bytes:
        return self.get_data()

    @builtin_method("__getitem__")
    @staticmethod
    def w_getitem(vm: "SPyVM", w_b: "W_Bytes", w_i: W_I32) -> W_I32:
        assert isinstance(w_b, W_Bytes)
        assert isinstance(w_i, W_I32)
        byte = vm.ll.call("spy_bytes_getitem", w_b.ptr, w_i.value)
        return vm.wrap(byte)

    @builtin_method("__len__")
    @staticmethod
    def w_len(vm: "SPyVM", w_b: "W_Bytes") -> W_I32:
        assert isinstance(w_b, W_Bytes)
        length = vm.ll.call("spy_bytes_len", w_b.ptr)
        return vm.wrap(length)

    @builtin_method("__str__")
    @staticmethod
    def w_str(vm: "SPyVM", w_b: "W_Bytes") -> W_Str:
        assert isinstance(w_b, W_Bytes)
        ptr = vm.ll.call("spy_bytes_repr", w_b.ptr)
        return W_Str.from_ptr(vm, ptr)

    @builtin_method("__repr__")
    @staticmethod
    def w_repr(vm: "SPyVM", w_b: "W_Bytes") -> W_Str:
        assert isinstance(w_b, W_Bytes)
        ptr = vm.ll.call("spy_bytes_repr", w_b.ptr)
        return W_Str.from_ptr(vm, ptr)
