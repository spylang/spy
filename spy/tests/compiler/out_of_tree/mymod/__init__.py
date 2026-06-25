from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from spy.build.build_info import BuildInfo, BuildTarget, BuildType
from spy.fqn import FQN
from spy.vm.b import B
from spy.vm.modules.unsafe.funcptr import W_CFuncPtr, W_CFuncPtrType
from spy.vm.primitive import W_I32
from spy.vm.registry import ModuleRegistry
from spy.vm.str import W_Str

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

HERE = Path(__file__).parent

MODULE = ModuleRegistry("mymod")

# c_func_ptr[i32, i32]: a callback that takes one i32 and returns i32
_w_cb_type = W_CFuncPtrType.from_signature(
    FQN("unsafe").join("c_func_ptr", [B.w_i32.fqn, B.w_i32.fqn]),
    B.w_i32,
    [B.w_i32],
)
CB = Annotated[W_CFuncPtr, _w_cb_type]


def build_info(target: BuildTarget, build_type: BuildType) -> BuildInfo:
    return BuildInfo(
        include_dirs=[f"{HERE}"],
        headers=[f"{HERE}/mymod.h"],
        archives=[f"{HERE}/build/{target}/{build_type}/libmymod.a"],
    )


@MODULE.builtin_func
def w_get_name(vm: "SPyVM") -> W_Str:
    return vm.wrap("hello from mymod")


@MODULE.builtin_func
def w_run_callback(vm: "SPyVM", w_cb: CB, w_x: W_I32) -> W_I32:
    # At interp level, w_cb is a W_CFuncPtr wrapping a W_ASTFunc.
    # Call the underlying function directly.
    assert isinstance(w_cb, W_CFuncPtr)
    return vm.fast_call(w_cb.w_func, [w_x])  # type: ignore[return-value]
