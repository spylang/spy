from typing import TYPE_CHECKING

from spy.vm.b import BUILTINS
from spy.vm.builtin import builtin_method
from spy.vm.function import W_Func
from spy.vm.object import W_Object

if TYPE_CHECKING:
    from spy.vm.opspec import W_MetaArg, W_OpSpec
    from spy.vm.vm import SPyVM


@BUILTINS.builtin_type("property", lazy_definition=True)
class W_Property(W_Object):

    def __init__(self, w_func: W_Func) -> None:
        self.w_func = w_func

    @builtin_method("__get__", color="blue", kind="metafunc")
    @staticmethod
    def w_GET(vm: "SPyVM", wam_self: "W_MetaArg", wam_o: "W_MetaArg") -> "W_OpSpec":
        w_prop = wam_self.w_blueval
        assert isinstance(w_prop, W_Property)
        w_func = w_prop.w_func
        return vm.fast_metacall(w_func, [wam_o])


@BUILTINS.builtin_type("staticmethod", lazy_definition=True)
class W_StaticMethod(W_Object):
    """
    The @staticmethod decorator.

    Currently support for it it's a bit ad-hoc. In particular,
    W_Type.w_CALL_METHOD has special logic to deal with it.

    Ideally, we would like to be able to use the normal descriptor protocol.
    """

    def __init__(self, w_obj: W_Object) -> None:
        self.w_obj = w_obj

    @builtin_method("__new__", color="blue")
    @staticmethod
    def w_new(vm: "SPyVM", w_obj: W_Object) -> "W_StaticMethod":
        return W_StaticMethod(w_obj)

    def __repr__(self) -> str:
        return f"<spy staticmethod {self.w_obj}>"


@BUILTINS.builtin_type("classmethod", lazy_definition=True)
class W_ClassMethod(W_Object):
    """
    The @classmethod decorator.

    Currently support for it it's a bit ad-hoc. In particular,
    W_Type.w_CALL_METHOD has special logic to deal with it.

    Ideally, we would like to be able to use the normal descriptor protocol.
    """

    def __init__(self, w_obj: W_Object) -> None:
        self.w_obj = w_obj

    @builtin_method("__new__", color="blue")
    @staticmethod
    def w_new(vm: "SPyVM", w_obj: W_Object) -> "W_ClassMethod":
        return W_ClassMethod(w_obj)

    def __repr__(self) -> str:
        return f"<spy classmethod {self.w_obj}>"
