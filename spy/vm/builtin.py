"""
This is NOT the spy "builtins" module.

This contains the basic machinery to build builtin functions and types, for
ALL builtin module. The builtin module whose name is "builtins" reside in
vm/modules/builtins.py.
"""

import inspect
from typing import (TYPE_CHECKING, Any, Callable, Type, Optional, get_origin,
                    Annotated)
from spy.fqn import FQN, QUALIFIERS
from spy.ast import Color
from spy.vm.object import W_Object, W_Type, make_metaclass_maybe, builtin_method
from spy.vm.function import FuncParam, FuncParamKind, W_FuncType, W_BuiltinFunc
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

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
      None -> B.w_void
    """
    from spy.vm.b import B
    if allow_None and ann is None:
        return B.w_void
    elif is_W_class(ann):
        return ann._w
    elif w_t := get_spy_type_annotation(ann):
        return w_t
    raise ValueError(f"Invalid @builtin_func annotation: {ann}")

def to_spy_FuncParam(p: Any, extra_types: TYPES_DICT) -> FuncParam:
    if p.name.startswith('w_'):
        name = p.name[2:]
    else:
        name = p.name
    #
    annotation = extra_types.get(p.annotation, p.annotation)
    w_type = to_spy_type(annotation)
    kind: FuncParamKind
    if p.kind == p.POSITIONAL_OR_KEYWORD:
        kind = 'simple'
    elif p.kind == p.VAR_POSITIONAL:
        kind = 'varargs'
    else:
        assert False
    return FuncParam(name, w_type, kind)


def functype_from_sig(fn: Callable, color: Color, *,
                      extra_types: dict = {}) -> W_FuncType:
    sig = inspect.signature(fn)
    params = list(sig.parameters.values())
    if len(params) == 0:
        msg = (f"The first param should be 'vm: SPyVM'. Got nothing")
        raise ValueError(msg)
    if (params[0].name != 'vm' or
        params[0].annotation != 'SPyVM'):
        msg = (f"The first param should be 'vm: SPyVM'. Got '{params[0]}'")
        raise ValueError(msg)

    func_params = [to_spy_FuncParam(p, extra_types) for p in params[1:]]
    ret_ann = extra_types.get(sig.return_annotation, sig.return_annotation)
    w_restype = to_spy_type(ret_ann, allow_None=True)
    return W_FuncType.new(func_params, w_restype, color=color)


def builtin_func(namespace: FQN|str,
                 funcname: Optional[str] = None,
                 qualifiers: QUALIFIERS = None,
                 *,
                 color: Color = 'red',
                 extra_types: dict = {},
                 ) -> Callable:
    """
    Decorator to make an interp-level function wrappable by the VM.

    Example of usage:

        @builtin_func("mymodule", "hello")
        def w_hello(vm: 'SPyVM', w_x: W_I32) -> W_Str:
            ...
        assert isinstance(w_hello, W_BuiltinFunc)
        assert w_hello.fqn == FQN("mymodule::hello")

    funcname can be omitted, and in that case it will automatically be deduced
    from __name__:

        @builtin_func("mymodule")
        def w_hello(vm: 'SPyVM', w_x: W_I32) -> W_Str:
            ...
        assert w_hello.fqn == FQN("mymodule::hello")


    The w_functype of the wrapped function is automatically computed by
    inspectng the signature of the interp-level function. The first parameter
    MUST be 'vm'.

    Note that the decorator returns a W_BuiltinFunc, which means that you
    cannot call it directly, but you need to use vm.call.
    """
    if isinstance(namespace, str):
        namespace = FQN(namespace)
    def decorator(fn: Callable) -> W_BuiltinFunc:
        assert fn.__name__.startswith('w_')
        fname = funcname
        if fname is None:
            fname = fn.__name__[2:]
        assert isinstance(namespace, FQN)
        fqn = namespace.join(fname, qualifiers)
        w_functype = functype_from_sig(fn, color, extra_types=extra_types)
        return W_BuiltinFunc(w_functype, fqn, fn)
    return decorator


def builtin_type(namespace: FQN|str,
                 typename: str,
                 qualifiers: QUALIFIERS = None,
                 *,
                 lazy_definition: bool = False
                 ) -> Any:
    """
    Class decorator to simplify the creation of builtin SPy types.

    Given a W_* class, it automatically creates the corresponding instance of
    W_Type and attaches it to the W_* class.
    """
    if isinstance(namespace, str):
        namespace = FQN(namespace)
    fqn = namespace.join(typename, qualifiers)
    def decorator(pyclass: Type[W_Object]) -> Type[W_Object]:
        W_MetaClass = make_metaclass_maybe(fqn, pyclass, lazy_definition)
        w_type = W_MetaClass.declare(fqn)
        if not lazy_definition:
            w_type.define(pyclass)
        pyclass._w = w_type
        return pyclass
    return decorator
