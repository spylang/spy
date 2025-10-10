from typing import TYPE_CHECKING, Annotated

from spy.fqn import FQN
from spy.vm.builtin import IRTag
from spy.vm.function import FuncParam, W_BuiltinFunc, W_FuncType
from spy.vm.member import Member
from spy.vm.object import W_Object, W_Type, builtin_method
from spy.vm.registry import ModuleRegistry
from spy.vm.str import W_Str
from spy.vm.tuple import W_Tuple

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

MLIR = ModuleRegistry("mlir")


@MLIR.builtin_type("MLIR_Type")
class W_MLIR_Type(W_Type):
    @builtin_method("__new__")
    @staticmethod
    def w_new(vm: "SPyVM", w_name: W_Str) -> "W_MLIR_Type":
        name = vm.unwrap_str(w_name)
        fqn = FQN(["mlir", "type", name])
        return W_MLIR_Type.from_pyclass(fqn, W_Object)


@MLIR.builtin_func("MLIR_op", color="blue")
def w_MLIR_op(
    vm: "SPyVM", w_opname: W_Str, w_restype: W_Type, w_argtypes: W_Tuple
) -> W_BuiltinFunc:
    RESTYPE = Annotated[W_Object, w_restype]
    opname = vm.unwrap_str(w_opname)
    argtypes_w = w_argtypes.items_w

    # functype
    params = [FuncParam(w_T, "simple") for w_T in argtypes_w]
    w_functype = W_FuncType.new(params, w_restype=w_restype)

    def w_opimpl(vm: "SPyVM", *args_w: W_Object) -> RESTYPE:
        raise NotImplementedError("MLIR ops are not supposed to be called")

    fqn = FQN(["mlir", "op", opname])
    w_op = W_BuiltinFunc(w_functype, fqn, w_opimpl)
    irtag = IRTag("mlir.op")  # we can add any extra metadata we want here
    vm.add_global(fqn, w_op, irtag=irtag)
    return w_op
