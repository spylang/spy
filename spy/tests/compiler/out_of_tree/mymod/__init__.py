from typing import TYPE_CHECKING

import py.path

from spy.vm.registry import CModuleBuildInfo, ModuleRegistry
from spy.vm.str import W_Str

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

_HERE = py.path.local(__file__).dirpath()

MODULE = ModuleRegistry("mymod")

MODULE.wasm_archives = [
    _HERE.join("build", "wasi", "libmymod.a"),
]

MODULE.build_info = CModuleBuildInfo(
    archive_specs=[(_HERE.join("build"), "libmymod.a")],
    include_dirs=[_HERE],
    headers=[_HERE.join("mymod.h")],
)


@MODULE.builtin_func
def w_get_name(vm: "SPyVM") -> W_Str:
    return vm.wrap("hello from mymod")
