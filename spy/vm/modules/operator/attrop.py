from typing import TYPE_CHECKING, Literal, no_type_check
from spy.fqn import QN
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type, W_Dynamic, W_Void
from spy.vm.module import W_Module
from spy.vm.str import W_Str
from spy.vm.function import W_Func
from spy.vm.sig import spy_builtin
from spy.vm.modules.types import W_TypeDef

from . import OP
from .binop import MM
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

OpKind = Literal['get', 'set']

@OP.builtin
def GETATTR(vm: 'SPyVM', w_type: W_Type, w_attr: W_Str) -> W_Dynamic:
    attr = vm.unwrap_str(w_attr)
    pyclass = w_type.pyclass
    if w_type is B.w_dynamic:
        raise NotImplementedError("implement me")
    elif attr in pyclass.__spy_members__:
        return opimpl_member('get', vm, w_type, attr)
    elif pyclass.has_meth_overriden('op_GETATTR'):
        return pyclass.op_GETATTR(vm, w_type, w_attr)

    # XXX refactor
    if isinstance(w_type, W_TypeDef) and w_type.w_getattr is not B.w_NotImplemented:
        w_getattr = w_type.w_getattr
        assert isinstance(w_getattr, W_Func)
        w_opimpl = vm.call_function(w_getattr, [w_type, w_attr])
        return w_opimpl

    if isinstance(w_type, W_TypeDef) and attr in w_type.__spy_descriptors__:
        w_descr = w_type.__spy_descriptors__[attr]
        #w_opimpl = w_descr.op_GET(vm, w_type, w_attr)
        assert w_descr.w_get.color == 'blue'
        w_opimpl = vm.call_function(w_descr.w_get, [w_descr])
        return w_opimpl

    return B.w_NotImplemented


@OP.builtin
def SETATTR(vm: 'SPyVM', w_type: W_Type, w_attr: W_Str,
            w_vtype: W_Type) -> W_Dynamic:
    attr = vm.unwrap_str(w_attr)
    pyclass = w_type.pyclass
    if w_type is B.w_dynamic:
        return OP.w_dynamic_setattr
    elif attr in pyclass.__spy_members__:
        return opimpl_member('set', vm, w_type, attr)
    elif pyclass.has_meth_overriden('op_SETATTR'):
        return pyclass.op_SETATTR(vm, w_type, w_attr, w_vtype)

    # XXX refactor
    if isinstance(w_type, W_TypeDef) and w_type.w_setattr is not B.w_NotImplemented:
        w_setattr = w_type.w_setattr
        assert isinstance(w_setattr, W_Func)
        w_opimpl = vm.call_function(w_setattr, [w_type, w_attr, w_vtype])
        return w_opimpl

    if isinstance(w_type, W_TypeDef) and attr in w_type.__spy_descriptors__:
        w_descr = w_type.__spy_descriptors__[attr]
        w_opimpl = w_descr.op_SET(vm, w_type, w_attr, w_vtype)
        return w_opimpl

    return B.w_NotImplemented


def opimpl_member(kind: OpKind, vm: 'SPyVM', w_type: W_Type,
                  attr: str) -> W_Dynamic:
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

        return vm.wrap(opimpl_get)

    elif kind == 'set':
        @no_type_check
        @spy_builtin(QN(modname=w_type.name, attr=f"__set_{attr}__"))
        def opimpl_set(vm: 'SPyVM', w_obj: W_Class, w_attr: W_Str,
                       w_val: W_Value) -> W_Void:
            setattr(w_obj, field, w_val)

        return vm.wrap(opimpl_set)

    else:
        assert False, f'Invalid OpKind: {kind}'
