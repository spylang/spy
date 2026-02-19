"""
This is NOT the spy "builtins" module.

This contains the basic machinery to build builtin functions and types, for
ALL builtin module. The builtin module whose name is "builtins" reside in
vm/modules/builtins.py.
"""

import inspect
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Callable,
    Optional,
    Type,
    get_origin,
)

from spy.ast import Color, FuncKind
from spy.errors import SPyError
from spy.fqn import FQN, QUALIFIERS
from spy.vm.function import FuncParam, FuncParamKind, W_BuiltinFunc, W_FuncType
from spy.vm.object import (
    W_Object,
    W_Type,
    builtin_class_attr,  # noqa: F401
    builtin_classmethod,
    builtin_method,
    builtin_property,
    builtin_staticmethod,
)

TYPES_DICT = dict[str, W_Type]


def is_W_class(x: Any) -> bool:
    return isinstance(x, type) and issubclass(x, W_Object)


def get_spy_type_annotation(ann: Any) -> Optional[W_Type]:
    if get_origin(ann) is Annotated:
        for x in ann.__metadata__:
            if isinstance(x, W_Type):
                return x
    return None


def to_spy_type(ann: Any, *, allow_None: bool = False) -> W_Type:
    """
    Convert an interp-level annotation into a spy type.
    Examples:
      W_I32 -> B.w_i32
      W_Dynamic -> B.w_dynamic
      Annotated[W_Object, w_mytype] -> w_mytype
      None -> TYPES.w_NoneType
    """
    from spy.vm.b import TYPES, B

    if allow_None and ann is None:
        return TYPES.w_NoneType
    elif is_W_class(ann):
        return ann._w
    elif w_t := get_spy_type_annotation(ann):
        return w_t
    raise ValueError(f"Invalid @builtin_func annotation: {ann}")


def to_spy_FuncParam(p: Any, extra_types: TYPES_DICT) -> FuncParam:
    annotation = extra_types.get(p.annotation, p.annotation)
    w_T = to_spy_type(annotation)
    kind: FuncParamKind
    if p.kind == p.POSITIONAL_OR_KEYWORD:
        kind = "simple"
    elif p.kind == p.VAR_POSITIONAL:
        kind = "var_positional"
    else:
        assert False
    return FuncParam(w_T, kind)


def functype_from_sig(
    fn: Callable, color: Color, kind: FuncKind, *, extra_types: dict = {}
) -> W_FuncType:
    sig = inspect.signature(fn)
    params = list(sig.parameters.values())
    if len(params) == 0:
        msg = f"The first param should be 'vm: SPyVM'. Got nothing"
        raise ValueError(msg)
    if params[0].name != "vm" or params[0].annotation != "SPyVM":
        msg = f"The first param should be 'vm: SPyVM'. Got '{params[0]}'"
        raise ValueError(msg)

    func_params = [to_spy_FuncParam(p, extra_types) for p in params[1:]]
    ret_ann = extra_types.get(sig.return_annotation, sig.return_annotation)
    w_restype = to_spy_type(ret_ann, allow_None=True)
    return W_FuncType.new(func_params, w_restype, color=color, kind=kind)


def make_builtin_func(
    fn: Callable,
    namespace: FQN | str,
    funcname: Optional[str] = None,
    qualifiers: QUALIFIERS = None,
    *,
    color: Color = "red",
    kind: FuncKind = "plain",
    extra_types: dict = {},
) -> W_BuiltinFunc:
    """
    Turn an interp-level function into a W_BuiltinFunc.
    See vm.register_builtin_func for additional docs.
    """
    if isinstance(namespace, str):
        namespace = FQN(namespace)
    assert fn.__name__.startswith("w_")
    fname = funcname
    if fname is None:
        fname = fn.__name__[2:]
    assert isinstance(namespace, FQN)
    fqn = namespace.join(fname, qualifiers)

    if kind == "metafunc" and color != "blue":
        msg = f"wrong color for metafunc `{fqn.human_name}`: expected `blue`, got `{color}`"
        raise SPyError("W_TypeError", msg)

    w_functype = functype_from_sig(fn, color, kind, extra_types=extra_types)
    return W_BuiltinFunc(w_functype, fqn, fn)


def builtin_type(
    namespace: FQN | str,
    typename: str,
    qualifiers: QUALIFIERS = None,
    *,
    lazy_definition: bool = False,
    W_MetaClass: Optional[Type[W_Type]] = None,
) -> Any:
    """
    Class decorator to simplify the creation of builtin SPy types.

    Given a W_* class, it automatically creates the corresponding instance of
    W_Type and attaches it to the W_* class.
    """
    if isinstance(namespace, str):
        namespace = FQN(namespace)
    if W_MetaClass is None:
        W_MetaClass = W_Type
    fqn = namespace.join(typename, qualifiers)

    def decorator(pyclass: Type[W_Object]) -> Type[W_Object]:
        assert issubclass(pyclass, W_Object)
        w_T = W_MetaClass.declare(fqn)
        if not lazy_definition:
            w_T.define(pyclass)
        pyclass._w = w_T
        return pyclass

    return decorator
