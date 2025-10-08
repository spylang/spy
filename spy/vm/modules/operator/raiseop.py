from typing import TYPE_CHECKING
from spy.location import Loc
from spy.errors import SPyError
from spy.vm.object import W_Type
from spy.vm.str import W_Str
from spy.vm.opspec import W_OpSpec, W_MetaArg
from spy.vm.opimpl import W_OpImpl
from spy.vm.primitive import W_I32
from spy.vm.exc import W_Exception

from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

@OP.builtin_func
def w_raise(vm: "SPyVM", w_etype: W_Str, w_message: W_Str,
            w_filename: W_Str, w_lineno: W_I32) -> None:
    etype = "W_" + vm.unwrap_str(w_etype)
    msg = vm.unwrap_str(w_message)
    fname = vm.unwrap_str(w_filename)
    lineno = vm.unwrap_i32(w_lineno)
    loc = Loc(fname, lineno, lineno, 1, -1)
    raise SPyError.simple(etype, msg, "", loc)

@OP.builtin_func(color="blue")
def w_RAISE(vm: "SPyVM", wam_exc: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec

    # We are doing a bit of magic here:
    #   1. manually turn the blue wam_exc into an hardcoded message
    #   2. return an w_opimpl which calls w_raise with the hardcoded message,
    #      ignoring the actual wam_exc
    if wam_exc.color != "blue":
        err = SPyError(
            "W_TypeError",
            "`raise` only accepts blue values for now",
        )
        err.add("error", "this is red", wam_exc.loc)
        raise err

    # we support two syntaxes:
    #   raise IndexError            # raise a type
    #   raise IndexError("hello")   # raise an instance
    w_exc = wam_exc.w_val
    if isinstance(w_exc, W_Type) and issubclass(w_exc.pyclass, W_Exception):
        # we are in the "raise IndexError" case
        etype = w_exc.pyclass.__name__ # "W_IndexError"
        msg = ""
    elif isinstance(w_exc, W_Exception):
        # we are in the "raise IndexError('hello')" case
        etype = w_exc.__class__.__name__
        msg = w_exc.message

    assert etype.startswith("W_")
    etype = etype[2:]
    w_etype = vm.wrap(etype)
    wam_etype = W_MetaArg.from_w_obj(vm, w_etype)

    w_msg = vm.wrap(msg)
    wam_msg = W_MetaArg.from_w_obj(vm, w_msg)

    w_fname = vm.wrap(wam_exc.loc.filename)
    wam_fname = W_MetaArg.from_w_obj(vm, w_fname)

    w_lineno = vm.wrap(wam_exc.loc.line_start)
    wam_lineno = W_MetaArg.from_w_obj(vm, w_lineno)

    w_opspec = W_OpSpec(OP.w_raise, [wam_etype, wam_msg, wam_fname, wam_lineno])

    return typecheck_opspec(
        vm,
        w_opspec,
        [wam_exc],
        dispatch="single",
        errmsg="cannot raise `{0}`"
    )
