"""
SPy `posix` module.
"""

from typing import TYPE_CHECKING, Annotated, Any

from spy.vm.b import B
from spy.vm.object import W_Object
from spy.vm.primitive import W_I32
from spy.vm.registry import ModuleRegistry
from spy.vm.str import W_Str
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


# ================= SPy stdio wrappers ===============
#
# These are SPy wrappers around FILE*, fopen, fclose, etc.
#
# Technically speaking they are part of libc, not posix, but I think that for now it's
# fine to keep them here.  This is temporary anyway, because the long term plan is that
# SPy's `file` object will be implemented directly in terms of open/read/write. But for
# now, we use fopen&co. because they give us buffering for free.


@POSIX.builtin_type("_FILE")
class W__FILE(W_Object):
    """
    XXX explain
    """

    __spy_storage_category__ = "value"
    h: int  # value of `FILE *`, casted to C `long`

    def __init__(self, h: int) -> None:
        self.h = h

    def spy_key(self, vm: "SPyVM") -> Any:
        return ("FILE *", self.h)


@POSIX.builtin_func
def w__fopen(vm: "SPyVM", w_filename: W_Str) -> W__FILE:
    h = vm.ll.call("spy_posix$_fopen", w_filename.ptr)
    return W__FILE(h)


@POSIX.builtin_func
def w__fread(vm: "SPyVM", w_f: W__FILE, w_size: W_I32) -> W_Str:
    ptr = vm.ll.call("spy_posix$_fread", w_f.h, w_size.value)
    return W_Str.from_ptr(vm, ptr)


@POSIX.builtin_func
def w__fclose(vm: "SPyVM", w_f: W__FILE) -> None:
    vm.ll.call("spy_posix$_fclose", w_f.h)
    return None
