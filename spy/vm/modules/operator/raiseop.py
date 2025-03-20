from typing import TYPE_CHECKING
from spy.errors import SPyError, SPyPanicError
from spy.vm.b import B
from spy.vm.object import W_Type
from spy.vm.str import W_Str
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.function import W_Func
from spy.vm.primitive import W_Dynamic, W_I32
from spy.vm.exc import W_Exception

from . import OP, op_fast_call
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

@OP.builtin_func
def w_panic(vm: 'SPyVM', w_message: W_Str,
            w_filename: W_Str, w_lineno: W_I32) -> None:
    msg = vm.unwrap_str(w_message)
    fname = vm.unwrap_str(w_filename)
    lineno = vm.unwrap_i32(w_lineno)
    raise SPyPanicError(msg, fname, lineno)

@OP.builtin_func(color='blue')
def w_RAISE(vm: 'SPyVM', wop_exc: W_OpArg) -> W_Func:
    from spy.vm.typechecker import typecheck_opimpl

    # We are doing a bit of magic here:
    #   1. manually turn the blue wop_exc into an hardcoded message
    #   2. return an w_opimpl which calls w_panic with the hardcoded message,
    #      ignoring the actual wop_exc
    if wop_exc.color != 'blue':
        err = SPyError("`raise` only accepts blue values for now",
                       etype='TypeError')
        err.add('error', 'this is red', wop_exc.loc)
        raise err

    # we support two syntaxes:
    #   raise IndexError            # raise a type
    #   raise IndexError("hello")   # raise an instance
    w_exc = wop_exc.w_val
    if isinstance(w_exc, W_Type) and issubclass(w_exc.pyclass, W_Exception):
        # we are in the "raise IndexError" case
        msg = w_exc.fqn.symbol_name
    elif isinstance(w_exc, W_Exception):
        # we are in the "raise IndexError('hello')" case
        msg = w_exc.spy_str(vm) # ==>  "IndexError: hello"

    w_msg = vm.wrap(msg)
    wop_msg = W_OpArg.from_w_obj(vm, w_msg)

    w_fname = vm.wrap(wop_exc.loc.filename)
    wop_fname = W_OpArg.from_w_obj(vm, w_fname)

    w_lineno = vm.wrap(wop_exc.loc.line_start)
    wop_lineno = W_OpArg.from_w_obj(vm, w_lineno)

    w_opimpl = W_OpImpl(OP.w_panic, [wop_msg, wop_fname, wop_lineno])

    return typecheck_opimpl(
        vm,
        w_opimpl,
        [wop_exc],
        dispatch='single',
        errmsg='cannot raise `{0}`'
    )
