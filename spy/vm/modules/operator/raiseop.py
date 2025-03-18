from typing import TYPE_CHECKING
from spy.errors import SPyTypeError, SPyPanicError
from spy.vm.b import B
from spy.vm.object import W_Type
from spy.vm.str import W_Str
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.function import W_Func
from spy.vm.primitive import W_Dynamic
from spy.vm.modules.builtins import W_Exception

from . import OP, op_fast_call
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

@OP.builtin_func
def w_panic(vm: 'SPyVM', w_message: W_Str) -> None:
    msg = vm.unwrap_str(w_message)
    raise SPyPanicError(msg)

@OP.builtin_func(color='blue')
def w_RAISE(vm: 'SPyVM', wop_exc: W_OpArg) -> W_Func:
    from spy.vm.typechecker import typecheck_opimpl

    # We are doing a bit of magic here:
    #   1. manually turn the blue wop_exc into an hardcoded message
    #   2. return an w_opimpl which calls w_panic with the hardcoded message,
    #      ignoring the actual wop_exc
    if wop_exc.color != 'blue':
        err = SPyTypeError("`raise` only accepts blue values for now")
        err.add('error', 'this is red', wop_exc.loc)
        raise err

    w_exc = wop_exc.w_val
    assert isinstance(w_exc, W_Exception) # XXX raise proper exception

    msg = w_exc.spy_str(vm) # this is e.g. "Exception: hello"
    w_msg = vm.wrap(msg)
    wop_msg = W_OpArg.from_w_obj(vm, w_msg)
    w_opimpl = W_OpImpl(OP.w_panic, [wop_msg])

    return typecheck_opimpl(
        vm,
        w_opimpl,
        [wop_exc],
        dispatch='single',
        errmsg='cannot raise `{0}`'
    )
