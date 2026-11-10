"""
<ai>SPy out-of-tree builtin VM module wrapping the CUI immediate-mode UI
library (https://github.com/yappologistic/CUI).

Load it with:

    spy --extra-vm-module ../spyvm_cui demo/counter.spy

or list it in spy.toml:

    extra-vm-modules = ["../spyvm_cui"]

CUI is a native GUI library (X11/OpenGL), so there is no WASI build. In
compiled mode the C backend links the native archive built by the Makefile.
In interpreted mode the same code is loaded through ctypes from a shared
library, so a window opens even without compiling the .spy program.</ai>

The C half lives in src/spyvm_cui.c. It exposes two families of functions:
  - `spy_cui$*`: the C-backend ABI, taking spy_StrObject pointers.
  - `pycui$*`:   the ctypes ABI, taking plain C strings.
"""

import ctypes
from pathlib import Path
from typing import TYPE_CHECKING, Any

from spy.build.build_info import BuildInfo, BuildTarget, BuildType
from spy.errors import SPyError
from spy.vm.primitive import W_F64, W_I32, W_Bool
from spy.vm.registry import ModuleRegistry
from spy.vm.str import W_Str

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

MODULE = ModuleRegistry("cui")

HERE = Path(__file__).parent
SOFILE = HERE / "build" / "interp" / "libspyvm_cui.so"


def build_info(target: BuildTarget, build_type: BuildType) -> BuildInfo:
    # <ai>CUI has no WASM build, so the interpreter has nothing to bundle and
    # uses ctypes instead. Only the native target is supported.</ai>
    if target != "native":
        return BuildInfo()
    return BuildInfo(
        include_dirs=[f"{HERE}/src", f"{HERE}/build/amalgamation"],
        headers=[f"{HERE}/src/spyvm_cui.h"],
        archives=[f"{HERE}/build/{target}/{build_type}/libspyvm_cui.a"],
        ldflags=["-lX11", "-ldl", "-lpthread", "-lm"],
    )


# ============================ ctypes plumbing ============================

_lib: Any = None


def _get_lib() -> Any:
    global _lib
    if _lib is not None:
        return _lib
    if not SOFILE.exists():
        raise SPyError(
            "W_NotImplementedError",
            f"cannot find {SOFILE}: build it with `make -C {HERE} interp`",
        )
    lib = ctypes.CDLL(str(SOFILE))
    cp = ctypes.c_char_p
    d = ctypes.c_double
    i32 = ctypes.c_int32
    b = ctypes.c_bool
    vp = ctypes.c_void_p
    sigs: dict[str, tuple[list[Any], Any]] = {
        "app_create": ([cp, i32, i32], vp),
        "app_frame": ([], b),
        "app_destroy": ([], None),
        "page_begin": ([], None),
        "page_end": ([], None),
        "column_begin": ([d, d], None),
        "column_fill_begin": ([d, d], None),
        "column_max_begin": ([d, d, d], None),
        "column_end": ([], None),
        "row_begin": ([d], None),
        "row_fill_begin": ([d], None),
        "row_end": ([], None),
        "scroll_begin": ([cp], None),
        "scroll_end": ([], None),
        "spacer": ([], None),
        "separator": ([], None),
        "heading": ([cp, i32], None),
        "text": ([cp], None),
        "secondary": ([cp], None),
        "label": ([cp], None),
        "badge": ([cp, i32], None),
        "toast": ([cp], None),
        "progress": ([d], None),
        "button": ([cp, b], b),
        "icon_button": ([cp], b),
        "switch": ([cp, b], b),
        "checkbox": ([cp, b], b),
        "slider": ([cp, d, d, d], d),
        "segmented": ([cp, cp, i32], i32),
        "input": ([cp, cp, cp], cp),
        "input_clear": ([cp], None),
        "input_submitted": ([], b),
        "input_changed": ([], b),
        "push_id_int": ([i32], None),
        "pop_id": ([], None),
        "dialog_begin": ([cp, cp, b], b),
        "dialog_end": ([], None),
        "dialog_footer_begin": ([], None),
        "dialog_footer_end": ([], None),
    }
    for name, (argtypes, restype) in sigs.items():
        fn = getattr(lib, f"pycui${name}")
        fn.argtypes = argtypes
        fn.restype = restype
    _lib = lib
    return lib


def _fn(name: str) -> Any:
    return getattr(_get_lib(), f"pycui${name}")


def _cs(w: W_Str) -> bytes:
    return w.get_utf8()


# ================================ the app ================================


@MODULE.builtin_func
def w_app_create(vm: "SPyVM", title: W_Str, width: W_I32, height: W_I32) -> W_Bool:
    res = _fn("app_create")(_cs(title), width.value, height.value)
    return vm.wrap(bool(res))


@MODULE.builtin_func
def w_app_frame(vm: "SPyVM") -> W_Bool:
    return vm.wrap(_fn("app_frame")())


@MODULE.builtin_func
def w_app_destroy(vm: "SPyVM") -> None:
    _fn("app_destroy")()


# =============================== containers ==============================


@MODULE.builtin_func
def w_page_begin(vm: "SPyVM") -> None:
    _fn("page_begin")()


@MODULE.builtin_func
def w_page_end(vm: "SPyVM") -> None:
    _fn("page_end")()


@MODULE.builtin_func
def w_column_begin(vm: "SPyVM", pad: W_F64, gap: W_F64) -> None:
    _fn("column_begin")(pad.value, gap.value)


@MODULE.builtin_func
def w_column_fill_begin(vm: "SPyVM", pad: W_F64, gap: W_F64) -> None:
    _fn("column_fill_begin")(pad.value, gap.value)


@MODULE.builtin_func
def w_column_max_begin(vm: "SPyVM", pad: W_F64, gap: W_F64, max_width: W_F64) -> None:
    _fn("column_max_begin")(pad.value, gap.value, max_width.value)


@MODULE.builtin_func
def w_column_end(vm: "SPyVM") -> None:
    _fn("column_end")()


@MODULE.builtin_func
def w_row_begin(vm: "SPyVM", gap: W_F64) -> None:
    _fn("row_begin")(gap.value)


@MODULE.builtin_func
def w_row_fill_begin(vm: "SPyVM", gap: W_F64) -> None:
    _fn("row_fill_begin")(gap.value)


@MODULE.builtin_func
def w_row_end(vm: "SPyVM") -> None:
    _fn("row_end")()


@MODULE.builtin_func
def w_scroll_begin(vm: "SPyVM", id: W_Str) -> None:
    _fn("scroll_begin")(_cs(id))


@MODULE.builtin_func
def w_scroll_end(vm: "SPyVM") -> None:
    _fn("scroll_end")()


@MODULE.builtin_func
def w_spacer(vm: "SPyVM") -> None:
    _fn("spacer")()


@MODULE.builtin_func
def w_separator(vm: "SPyVM") -> None:
    _fn("separator")()


# ================================ widgets ================================


@MODULE.builtin_func
def w_heading(vm: "SPyVM", text: W_Str, level: W_I32) -> None:
    _fn("heading")(_cs(text), level.value)


@MODULE.builtin_func
def w_text(vm: "SPyVM", text: W_Str) -> None:
    _fn("text")(_cs(text))


@MODULE.builtin_func
def w_secondary(vm: "SPyVM", text: W_Str) -> None:
    _fn("secondary")(_cs(text))


@MODULE.builtin_func
def w_label(vm: "SPyVM", text: W_Str) -> None:
    _fn("label")(_cs(text))


@MODULE.builtin_func
def w_badge(vm: "SPyVM", text: W_Str, tone: W_I32) -> None:
    _fn("badge")(_cs(text), tone.value)


@MODULE.builtin_func
def w_toast(vm: "SPyVM", text: W_Str) -> None:
    _fn("toast")(_cs(text))


@MODULE.builtin_func
def w_progress(vm: "SPyVM", value: W_F64) -> None:
    _fn("progress")(value.value)


@MODULE.builtin_func
def w_button(vm: "SPyVM", label: W_Str, primary: W_Bool) -> W_Bool:
    return vm.wrap(_fn("button")(_cs(label), primary.value))


@MODULE.builtin_func
def w_icon_button(vm: "SPyVM", icon: W_Str) -> W_Bool:
    return vm.wrap(_fn("icon_button")(_cs(icon)))


@MODULE.builtin_func
def w_switch(vm: "SPyVM", label: W_Str, value: W_Bool) -> W_Bool:
    return vm.wrap(_fn("switch")(_cs(label), value.value))


@MODULE.builtin_func
def w_checkbox(vm: "SPyVM", label: W_Str, value: W_Bool) -> W_Bool:
    return vm.wrap(_fn("checkbox")(_cs(label), value.value))


@MODULE.builtin_func
def w_slider(vm: "SPyVM", label: W_Str, value: W_F64, lo: W_F64, hi: W_F64) -> W_F64:
    return vm.wrap(_fn("slider")(_cs(label), value.value, lo.value, hi.value))


@MODULE.builtin_func
def w_segmented(vm: "SPyVM", id: W_Str, items: W_Str, index: W_I32) -> W_I32:
    return vm.wrap(_fn("segmented")(_cs(id), _cs(items), index.value))


@MODULE.builtin_func
def w_input(vm: "SPyVM", id: W_Str, label: W_Str, placeholder: W_Str) -> W_Str:
    res = _fn("input")(_cs(id), _cs(label), _cs(placeholder))
    return vm.wrap(res.decode("utf-8"))


@MODULE.builtin_func
def w_input_clear(vm: "SPyVM", id: W_Str) -> None:
    _fn("input_clear")(_cs(id))


@MODULE.builtin_func
def w_input_submitted(vm: "SPyVM") -> W_Bool:
    return vm.wrap(_fn("input_submitted")())


@MODULE.builtin_func
def w_input_changed(vm: "SPyVM") -> W_Bool:
    return vm.wrap(_fn("input_changed")())


@MODULE.builtin_func
def w_push_id_int(vm: "SPyVM", n: W_I32) -> None:
    _fn("push_id_int")(n.value)


@MODULE.builtin_func
def w_pop_id(vm: "SPyVM") -> None:
    _fn("pop_id")()


@MODULE.builtin_func
def w_dialog_begin(
    vm: "SPyVM", title: W_Str, description: W_Str, open: W_Bool
) -> W_Bool:
    return vm.wrap(_fn("dialog_begin")(_cs(title), _cs(description), open.value))


@MODULE.builtin_func
def w_dialog_end(vm: "SPyVM") -> None:
    _fn("dialog_end")()


@MODULE.builtin_func
def w_dialog_footer_begin(vm: "SPyVM") -> None:
    _fn("dialog_footer_begin")()


@MODULE.builtin_func
def w_dialog_footer_end(vm: "SPyVM") -> None:
    _fn("dialog_footer_end")()
