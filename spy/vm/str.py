from typing import TYPE_CHECKING
from spy.llwasm import LLWasmInstance
from spy.vm.b import B, BUILTINS
from spy.vm.object import W_Object, W_Type
from spy.vm.builtin import builtin_method
from spy.vm.opspec import W_OpSpec, W_MetaArg
from spy.vm.primitive import W_I32, W_F64
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


@B.builtin_type('str', lazy_definition=True)
class W_Str(W_Object):
    """
    An unicode string, internally represented as UTF-8.

    This is basically a 'spy_Str *', i.e. a pointer to a C struct which
    resides in the linear memory of the VM:
        typedef struct {
            size_t length;
            const char utf8[];
        } spy_Str;
    """
    __spy_storage_category__ = 'value'
    vm: 'SPyVM'
    ptr: int

    def __init__(self, vm: 'SPyVM', s: str) -> None:
        ptr = ll_spy_Str_new(vm.ll, s)
        self.vm = vm
        self.ptr = ptr

    @staticmethod
    def from_ptr(vm: 'SPyVM', ptr: int) -> 'W_Str':
        w_res = W_Str.__new__(W_Str)
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
        return f'W_Str({s!r})'

    def spy_unwrap(self, vm: 'SPyVM') -> str:
        return self._as_str()

    def spy_key(self, vm: 'SPyVM') -> str:
        return self._as_str()

    @builtin_method('__new__', color='blue', kind='metafunc')
    @staticmethod
    def w_NEW(vm: 'SPyVM', wam_cls: W_MetaArg, *args_wam: W_MetaArg) -> 'W_OpSpec':
        from spy.vm.b import B
        if len(args_wam) == 1:
            wam_arg = args_wam[0]
            if wam_arg.w_static_T is B.w_i32:
                return W_OpSpec(w_int2str, [wam_arg])
            elif wam_arg.w_static_T is B.w_f64:
                return W_OpSpec(w_float2str, [wam_arg])
        return W_OpSpec.NULL

    @builtin_method('__getitem__')
    @staticmethod
    def w_getitem(vm: 'SPyVM', w_s: 'W_Str', w_i: W_I32) -> 'W_Str':
        assert isinstance(w_s, W_Str)
        assert isinstance(w_i, W_I32)
        ptr_c = vm.ll.call('spy_str_getitem', w_s.ptr, w_i.value)
        return W_Str.from_ptr(vm, ptr_c)

    @builtin_method('__len__')
    @staticmethod
    def w_len(vm: 'SPyVM', w_s: 'W_Str') -> W_I32:
        assert isinstance(w_s, W_Str)
        length = vm.ll.call('spy_str_len', w_s.ptr)
        return vm.wrap(length)


@BUILTINS.builtin_func(hidden=True)
def w_int2str(vm: 'SPyVM', w_i: W_I32) -> W_Str:
    i = vm.unwrap_i32(w_i)
    return vm.wrap(str(i))


@BUILTINS.builtin_func(hidden=True)
def w_float2str(vm: 'SPyVM', w_f: W_F64) -> W_Str:
    f = vm.unwrap_f64(w_f)
    return vm.wrap(str(f))
