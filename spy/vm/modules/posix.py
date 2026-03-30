"""
SPy `posix` module.
"""

from typing import TYPE_CHECKING, Annotated

from spy.errors import SPyError
from spy.vm.b import B
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


@POSIX.builtin_func("__INIT__", color="blue")
def w_INIT(vm: "SPyVM") -> None:
    import os

    w_mod = vm.modules_w["posix"]
    # Expose the most common O_* flags as module-level constants
    for name in (
        "O_RDONLY",
        "O_WRONLY",
        "O_RDWR",
        "O_APPEND",
        "O_CREAT",
        "O_TRUNC",
        "O_EXCL",
    ):
        if hasattr(os, name):
            w_mod.setattr(name, W_I32(getattr(os, name)))


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


@POSIX.builtin_func
def w_open(vm: "SPyVM", w_path: W_Str, w_flags: W_I32) -> W_I32:
    import os

    path = vm.unwrap_str(w_path)
    flags = w_flags.value
    try:
        fd = os.open(path, flags)
    except OSError as e:
        raise SPyError("W_OSError", e.strerror or "unknown error")
    return W_I32(fd)


@POSIX.builtin_func
def w_read(vm: "SPyVM", w_fd: W_I32, w_count: W_I32) -> W_Str:
    import os

    fd = w_fd.value
    count = w_count.value
    try:
        data = os.read(fd, count)
    except OSError as e:
        raise SPyError("W_OSError", e.strerror or "unknown error")
    return W_Str(vm, data.decode("utf-8"))


@POSIX.builtin_func
def w_write(vm: "SPyVM", w_fd: W_I32, w_data: W_Str) -> W_I32:
    import os

    fd = w_fd.value
    data = vm.unwrap_str(w_data).encode("utf-8")
    try:
        n = os.write(fd, data)
    except OSError as e:
        raise SPyError("W_OSError", e.strerror or "unknown error")
    return W_I32(n)


@POSIX.builtin_func
def w_close(vm: "SPyVM", w_fd: W_I32) -> None:
    import os

    fd = w_fd.value
    try:
        os.close(fd)
    except OSError as e:
        raise SPyError("W_OSError", e.strerror or "unknown error")
