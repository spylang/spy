from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from spy.build.build_info import BuildInfo, BuildTarget, BuildType
from spy.vm.b import B
from spy.vm.function import FuncParam, W_Func, W_FuncType
from spy.vm.primitive import W_I32
from spy.vm.registry import ModuleRegistry
from spy.vm.str import W_Str

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

HERE = Path(__file__).parent

MODULE = ModuleRegistry("mymod")

# red def(i32) -> i32: a callback that takes one i32 and returns i32
_w_cb_type = W_FuncType.new([FuncParam(B.w_i32, "simple")], B.w_i32)
CB = Annotated[W_Func, _w_cb_type]


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
    # At interp level, w_cb is the W_ASTFunc itself. Call it directly.
    assert isinstance(w_cb, W_Func)
    return vm.fast_call(w_cb, [w_x])  # type: ignore[return-value]
