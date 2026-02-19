"""
SPy `posix` module.
"""

from typing import TYPE_CHECKING, Annotated

from spy.vm.b import B
from spy.vm.primitive import W_I32
from spy.vm.registry import ModuleRegistry
from spy.vm.struct import W_Struct

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

POSIX = ModuleRegistry("posix")

# NOTE: this struct is also defined in posix.h, the two definitions must be kept in sync
POSIX.struct_type(
    "TerminalSize",
    [
        ("columns", B.w_i32),
        ("lines", B.w_i32),
    ],
    builtin=True,
)

W_TerminalSize = Annotated[W_Struct, POSIX.w_TerminalSize]


@POSIX.builtin_func
def w_get_terminal_size(vm: "SPyVM") -> W_TerminalSize:
    import os

    try:
        size = os.get_terminal_size()
        columns, lines = size.columns, size.lines
    except OSError:
        # Fallback when no terminal is available (e.g., in tests)
        columns, lines = 80, 24
    w_st = W_Struct(POSIX.w_TerminalSize)
    w_st.values_w = {"columns": W_I32(columns), "lines": W_I32(lines)}
    return w_st
