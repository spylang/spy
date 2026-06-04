from typing import TYPE_CHECKING

from spy.fqn import FQN
from spy.libspy import LLSPyInstance
from spy.vm.b import BUILTINS, OP, B
from spy.vm.builtin import builtin_method
from spy.vm.object import W_Object, W_Type
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.primitive import W_F64, W_I32

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


def ll_str_new(ll: LLSPyInstance, s: str) -> int:
    """
    Create a new spy_StrObject object inside the given LLWasmInstance, and fill it
    with the utf8-encoded content of s.

    Return the corresponding 'spy_StrObject *'
    """
    utf8 = s.encode("utf-8")
    length = len(utf8)
    ptr = ll.call("spy_str_alloc", length)
    utf8_ptr = ll.mem.read_i32(ptr + ll.str_layout.utf8_offset)
    ll.mem.write(utf8_ptr, utf8)
    return ptr


@B.builtin_type("str", lazy_definition=True)
class W_Str(W_Object):
    """
    An unicode string, internally represented as UTF-8.

    This is basically a 'spy_StrObject *', i.e. a pointer to a C struct which
    resides in the linear memory of the VM:
        typedef struct {
            size_t length;
            int32_t hash;
            const char utf8[];
        } spy_StrObject;
    """

    __spy_storage_category__ = "value"
    __spy_lazy_attributes__ = {
        "isascii": FQN("_str::methods::isascii"),
        "upper": FQN("_str::methods::upper"),
    }

    vm: "SPyVM"
    ptr: int

    def __init__(self, vm: "SPyVM", s: str) -> None:
        ptr = ll_str_new(vm.ll, s)
        self.vm = vm
        self.ptr = ptr

    @staticmethod
    def from_ptr(vm: "SPyVM", ptr: int) -> "W_Str":
        w_res = W_Str.__new__(W_Str)
        w_res.vm = vm
        w_res.ptr = ptr
        return w_res

    def get_length(self) -> int:
        ll = self.vm.ll
        return ll.mem.read_i32(self.ptr + ll.str_layout.length_offset)

    def get_utf8(self) -> bytes:
        _, _, utf8 = self.vm.ll.read_str(self.ptr)
        return utf8

    def _as_str(self) -> str:
        return self.get_utf8().decode("utf-8")

    def __repr__(self) -> str:
        s = self._as_str()
        return f"W_Str({s!r})"

    def spy_unwrap(self, vm: "SPyVM") -> str:
        return self._as_str()

    def spy_key(self, vm: "SPyVM") -> str:
        return self._as_str()

    @builtin_method("__new__", color="blue", kind="metafunc")
    @staticmethod
    def w_NEW(vm: "SPyVM", wam_cls: W_MetaArg, *args_wam: W_MetaArg) -> "W_OpSpec":
        from spy.errors import SPyError

        if len(args_wam) == 1:
            wam_arg = args_wam[0]
            w_T = wam_arg.w_static_T
            if w_T is B.w_dynamic:
                return W_OpSpec(OP.w_dynamic_str, [wam_arg])
            if w_fn := w_T.lookup_func(vm, "__str__"):
                w_opspec = vm.fast_metacall(w_fn, [wam_arg])
                return w_opspec

            t = w_T.fqn.human_name(vm)
            raise SPyError.simple(
                "W_TypeError", f"cannot call str(`{t}`)", f"this is `{t}`", wam_arg.loc
            )
        return W_OpSpec.NULL

    @builtin_method("__getitem__")
    @staticmethod
    def w_getitem(vm: "SPyVM", w_s: "W_Str", w_i: W_I32) -> "W_Str":
        assert isinstance(w_s, W_Str)
        assert isinstance(w_i, W_I32)
        ptr_c = vm.ll.call("spy_str_getitem", w_s.ptr, w_i.value)
        return W_Str.from_ptr(vm, ptr_c)

    @builtin_method("__len__")
    @staticmethod
    def w_len(vm: "SPyVM", w_s: "W_Str") -> W_I32:
        assert isinstance(w_s, W_Str)
        length = vm.ll.call("spy_str_len", w_s.ptr)
        return vm.wrap(length)

    @builtin_method("__str__")
    @staticmethod
    def w_str(vm: "SPyVM", w_s: "W_Str") -> "W_Str":
        return w_s

    @builtin_method("__repr__")
    @staticmethod
    def w_repr(vm: "SPyVM", w_s: "W_Str") -> "W_Str":
        assert isinstance(w_s, W_Str)
        ptr = vm.ll.call("spy_str_repr", w_s.ptr)
        return W_Str.from_ptr(vm, ptr)

    @builtin_method("replace")
    @staticmethod
    def w_replace(
        vm: "SPyVM", w_original: "W_Str", w_old: "W_Str", w_new: "W_Str"
    ) -> "W_Str":
        ptr_c = vm.ll.call("spy_str_replace", w_original.ptr, w_old.ptr, w_new.ptr)
        return W_Str.from_ptr(vm, ptr_c)
