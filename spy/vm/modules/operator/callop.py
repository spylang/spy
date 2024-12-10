from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type
from spy.vm.primitive import W_Dynamic
from spy.vm.str import W_Str
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.function import W_DirectCall, W_FuncType, FuncParam, W_Func

from . import OP
from .binop import MM
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.builtin_func(color='blue')
def w_CALL(vm: 'SPyVM', wop_obj: W_OpArg, *args_wop: W_OpArg) -> W_Func:
    from spy.vm.typechecker import typecheck_opimpl
    w_opimpl = W_OpImpl.NULL
    w_type = wop_obj.w_static_type
    pyclass = w_type.pyclass
    if w_type is B.w_dynamic:
        #w_opimpl = W_OpImpl(OP.w_dynamic_call)  # see _dynamic_call_opimpl
        w_opimpl = _dynamic_call_opimpl(list(args_wop))
    elif pyclass.has_meth_overriden('op_CALL'):
        w_opimpl = pyclass.op_CALL(vm, wop_obj, *args_wop)

    return typecheck_opimpl(
        vm,
        w_opimpl,
        [wop_obj] + list(args_wop),
        dispatch = 'single',
        errmsg = 'cannot call objects of type `{0}`'
    )


def _dynamic_call_opimpl(args_wop: list[W_OpArg]) -> W_OpImpl:
    """
    This is a hack, and it's half wrong.

    Ideally, we would like to do this in w_CALL above:
        if w_type is B.w_dynamic:
            w_opimpl = W_OpImpl(OP.w_dynamic_call)

    But in order for it to work, we need more goodies, like the ability of
    comparing two W_FuncType by equality (because e.g. for test_unsafe they
    end up in the bluecache).

    The temporary workaround is to pretend that this is a direct call: for
    this, we fabricate a fake w_functype which takes the right number of
    arguments, to ensure that we pass the typechecking.

    The half-right part is that this works well if the dynamic object turns
    out to be actually a W_Func, and no type conversions are necessary.
    The half-wrong part is that this breaks in all other cases, but for now
    it's good enough.
    """
    N  = len(args_wop)
    w_functype = W_FuncType(
        params = [FuncParam(f'v{i}', B.w_dynamic, 'simple') for i in range(N)],
        w_restype = B.w_dynamic
    )
    return W_OpImpl(
        W_DirectCall(w_functype),
        args_wop
    )


@OP.builtin_func(color='blue')
def w_CALL_METHOD(vm: 'SPyVM', wop_obj: W_OpArg, wop_method: W_OpArg,
                  *args_wop: W_OpArg) -> W_Func:
    from spy.vm.typechecker import typecheck_opimpl
    w_opimpl = W_OpImpl.NULL
    w_type = wop_obj.w_static_type
    pyclass = w_type.pyclass
    if pyclass.has_meth_overriden('op_CALL_METHOD'):
        w_opimpl = pyclass.op_CALL_METHOD(vm, wop_obj, wop_method, *args_wop)

    return typecheck_opimpl(
        vm,
        w_opimpl,
        [wop_obj, wop_method] + list(args_wop),
        dispatch = 'single',
        errmsg = 'cannot call methods on type `{0}`'
    )
