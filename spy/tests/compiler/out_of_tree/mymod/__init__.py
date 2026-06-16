from pathlib import Path
from typing import TYPE_CHECKING

from spy.build.build_info import BuildInfo, BuildTarget, BuildType
from spy.vm.registry import ModuleRegistry
from spy.vm.str import W_Str

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

HERE = Path(__file__).parent

MODULE = ModuleRegistry("mymod")


def build_info(target: BuildTarget, build_type: BuildType) -> BuildInfo:
    return BuildInfo(
        include_dirs=[f"{HERE}"],
        headers=[f"{HERE}/mymod.h"],
        archives=[f"{HERE}/build/{target}/{build_type}/libmymod.a"],
    )


@MODULE.builtin_func
def w_get_name(vm: "SPyVM") -> W_Str:
    return vm.wrap("hello from mymod")
