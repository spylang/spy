from typing import TYPE_CHECKING, Literal, no_type_check
from spy.fqn import QN
from spy.vm.primitive import W_Void
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type, W_Dynamic
from spy.vm.module import W_Module
from spy.vm.str import W_Str
from spy.vm.function import W_Func
from spy.vm.builtin import builtin_func
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.modules.types import W_TypeDef

from . import OP
from .binop import MM
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

OpKind = Literal['get', 'set']

def unwrap_attr_maybe(vm: 'SPyVM', wop_attr: W_OpArg) -> str:
    if wop_attr.is_blue() and wop_attr.w_static_type is B.w_str:
        return vm.unwrap_str(wop_attr.w_blueval)
    else:
        return '<unknown>'

@OP.builtin_func(color='blue')
def w_GETATTR(vm: 'SPyVM', wop_obj: W_OpArg, wop_attr: W_OpArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opimpl
    attr = unwrap_attr_maybe(vm, wop_attr)
    w_opimpl = _get_GETATTR_opimpl(vm, wop_obj, wop_attr, attr)
    typecheck_opimpl(
        vm,
        w_opimpl,
        [wop_obj, wop_attr],
        dispatch = 'single',
        errmsg = "type `{0}` has no attribute '%s'" % attr
    )
    return w_opimpl

def _get_GETATTR_opimpl(vm: 'SPyVM', wop_obj: W_OpArg, wop_attr: W_OpArg,
                        attr: str) -> W_OpImpl:
    w_type = wop_obj.w_static_type
    pyclass = w_type.pyclass
    if w_type is B.w_dynamic:
        raise NotImplementedError("implement me")
    elif attr in pyclass.__spy_members__:
        return opimpl_member('get', vm, w_type, attr)
    elif pyclass.has_meth_overriden('op_GETATTR'):
        return pyclass.op_GETATTR(vm, wop_obj, wop_attr)

    # until commit fc4ff1b we had special logic for typedef. At some point we
    # either need to resume it or kill typedef entirely.
    return W_OpImpl.NULL


@OP.builtin_func(color='blue')
def w_SETATTR(vm: 'SPyVM', wop_obj: W_OpArg, wop_attr: W_OpArg,
            wop_v: W_OpArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opimpl
    attr = unwrap_attr_maybe(vm, wop_attr)
    w_opimpl = _get_SETATTR_opimpl(vm, wop_obj, wop_attr, wop_v, attr)
    errmsg = "type `{0}` does not support assignment to attribute '%s'" % attr
    typecheck_opimpl(
        vm,
        w_opimpl,
        [wop_obj, wop_attr, wop_v],
        dispatch = 'single',
        errmsg = errmsg
    )
    return w_opimpl

def _get_SETATTR_opimpl(vm: 'SPyVM', wop_obj: W_OpArg, wop_attr: W_OpArg,
                        wop_v: W_OpArg, attr: str) -> W_OpImpl:
    w_type = wop_obj.w_static_type
    pyclass = w_type.pyclass
    if w_type is B.w_dynamic:
        return W_OpImpl(OP.w_dynamic_setattr)
    elif attr in pyclass.__spy_members__:
        return opimpl_member('set', vm, w_type, attr)
    elif pyclass.has_meth_overriden('op_SETATTR'):
        return pyclass.op_SETATTR(vm, wop_obj, wop_attr, wop_v)

    # until commit fc4ff1b we had special logic for typedef. At some point we
    # either need to resume it or kill typedef entirely.
    return W_OpImpl.NULL


def opimpl_member(kind: OpKind, vm: 'SPyVM', w_type: W_Type,
                  attr: str) -> W_OpImpl:
    pyclass = w_type.pyclass
    member = pyclass.__spy_members__[attr]
    W_Class = pyclass
    W_OpArg = member.w_type.pyclass
    field = member.field # the interp-level name of the attr (e.g, 'w_x')

    # XXX FIXME QNs are slightly wrong because they uses the type name as the
    # modname. We need to rethink how QNs are computed

    if kind == 'get':
        @no_type_check
        @builtin_func(QN([w_type.name, f"__get_{attr}__"]))
        def w_opimpl_get(vm: 'SPyVM', w_obj: W_Class, w_attr: W_Str) -> W_OpArg:
            return getattr(w_obj, field)

        return W_OpImpl(w_opimpl_get)

    elif kind == 'set':
        @no_type_check
        @builtin_func(QN([w_type.name, f"__set_{attr}__"]))
        def w_opimpl_set(vm: 'SPyVM', w_obj: W_Class, w_attr: W_Str,
                         w_val: W_OpArg) -> W_Void:
            setattr(w_obj, field, w_val)

        return W_OpImpl(w_opimpl_set)

    else:
        assert False, f'Invalid OpKind: {kind}'
