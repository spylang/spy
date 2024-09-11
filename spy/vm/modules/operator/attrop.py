from typing import TYPE_CHECKING, Literal, no_type_check
from spy.fqn import QN
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type, W_Dynamic, W_Void
from spy.vm.module import W_Module
from spy.vm.str import W_Str
from spy.vm.function import W_Func
from spy.vm.sig import spy_builtin
from spy.vm.opimpl import W_OpImpl, W_Value
from spy.vm.modules.types import W_TypeDef

from . import OP
from .binop import MM
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

OpKind = Literal['get', 'set']

@OP.builtin(color='blue')
def GETATTR(vm: 'SPyVM', wv_obj: W_Value, wv_attr: W_Value) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opimpl
    if wv_attr.is_blue() and wv_attr.w_static_type is B.w_str:
        attr = vm.unwrap_str(wv_attr.w_blueval)
    else:
        attr = '<unknown>'

    w_opimpl = _get_GETATTR_opimpl(vm, wv_obj, wv_attr, attr)
    typecheck_opimpl(
        vm,
        w_opimpl,
        [wv_obj, wv_attr],
        dispatch = 'single',
        errmsg = "type `{0}` has no attribute '%s'" % attr
    )
    return w_opimpl

def _get_GETATTR_opimpl(vm: 'SPyVM', wv_obj: W_Value, wv_attr: W_Value,
                        attr: str) -> W_OpImpl:
    w_type = wv_obj.w_static_type
    pyclass = w_type.pyclass
    if w_type is B.w_dynamic:
        raise NotImplementedError("implement me")
    elif attr in pyclass.__spy_members__:
        XXX
        return opimpl_member('get', vm, w_type, attr)
    elif pyclass.has_meth_overriden('op_GETATTR'):
        return pyclass.op_GETATTR(vm, wv_obj, wv_attr)

    # XXX refactor
    if isinstance(w_type, W_TypeDef) and w_type.w_getattr is not None:
        XXX
        w_getattr = w_type.w_getattr
        assert isinstance(w_getattr, W_Func)
        w_func = vm.call(w_getattr, [w_type, w_attr])
        assert isinstance(w_func, W_Func)
        # XXX: ideally, we should be able to return directly an W_OpImpl from
        # applevel
        return W_OpImpl.simple(w_func)

    return W_OpImpl.NULL


@OP.builtin(color='blue')
def SETATTR(vm: 'SPyVM', w_type: W_Type, w_attr: W_Str,
            w_vtype: W_Type) -> W_OpImpl:
    attr = vm.unwrap_str(w_attr)
    pyclass = w_type.pyclass
    if w_type is B.w_dynamic:
        return W_OpImpl.simple(OP.w_dynamic_setattr)
    elif attr in pyclass.__spy_members__:
        return opimpl_member('set', vm, w_type, attr)
    elif pyclass.has_meth_overriden('op_SETATTR'):
        return pyclass.op_SETATTR(vm, w_type, w_attr, w_vtype)

    # XXX refactor
    if isinstance(w_type, W_TypeDef) and w_type.w_setattr is not None:
        w_setattr = w_type.w_setattr
        assert isinstance(w_setattr, W_Func)
        w_func = vm.call(w_setattr, [w_type, w_attr, w_vtype])
        assert isinstance(w_func, W_Func)
        return W_OpImpl.simple(w_func)

    return W_OpImpl.NULL


def opimpl_member(kind: OpKind, vm: 'SPyVM', w_type: W_Type,
                  attr: str) -> W_OpImpl:
    pyclass = w_type.pyclass
    member = pyclass.__spy_members__[attr]
    W_Class = pyclass
    W_Value = member.w_type.pyclass
    field = member.field # the interp-level name of the attr (e.g, 'w_x')

    # XXX QNs are slightly wrong because they uses the type name as the
    # modname. We need to rethink how QNs are computed

    if kind == 'get':
        @no_type_check
        @spy_builtin(QN(modname=w_type.name, attr=f"__get_{attr}__"))
        def opimpl_get(vm: 'SPyVM', w_obj: W_Class, w_attr: W_Str) -> W_Value:
            return getattr(w_obj, field)

        return W_OpImpl.simple(vm.wrap_func(opimpl_get))

    elif kind == 'set':
        @no_type_check
        @spy_builtin(QN(modname=w_type.name, attr=f"__set_{attr}__"))
        def opimpl_set(vm: 'SPyVM', w_obj: W_Class, w_attr: W_Str,
                       w_val: W_Value) -> W_Void:
            setattr(w_obj, field, w_val)

        return W_OpImpl.simple(vm.wrap_func(opimpl_set))

    else:
        assert False, f'Invalid OpKind: {kind}'
