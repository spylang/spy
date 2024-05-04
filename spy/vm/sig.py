import inspect
from typing import TYPE_CHECKING, Any, Callable
from spy.fqn import QN
from spy.vm.object import W_Object, W_Type, W_Dynamic, w_DynamicType, W_Void
from spy.vm.function import FuncParam, W_FuncType, W_BuiltinFunc
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

# we cannot import B due to circular imports, let's fake it
B_w_dynamic = w_DynamicType
B_w_Void = W_Void._w

def is_W_class(x: Any) -> bool:
    return isinstance(x, type) and issubclass(x, W_Object)


def to_spy_FuncParam(p: Any) -> FuncParam:
    if p.name.startswith('w_'):
        name = p.name[2:]
    else:
        name = p.name
    #
    pyclass = p.annotation
    if pyclass is W_Dynamic:
        return FuncParam(name, B_w_dynamic)
    elif issubclass(pyclass, W_Object):
        return FuncParam(name, pyclass._w)
    else:
        raise ValueError(f"Invalid param: '{p}'")


def functype_from_sig(fn: Callable) -> W_FuncType:
    sig = inspect.signature(fn)
    params = list(sig.parameters.values())
    if len(params) == 0:
        msg = (f"The first param should be 'vm: SPyVM'. Got nothing")
        raise ValueError(msg)
    if (params[0].name != 'vm' or
        params[0].annotation != 'SPyVM'):
        msg = (f"The first param should be 'vm: SPyVM'. Got '{params[0]}'")
        raise ValueError(msg)

    func_params = [to_spy_FuncParam(p) for p in params[1:]]
    ret = sig.return_annotation
    if ret is None:
        w_restype = B_w_Void
    elif ret is W_Dynamic:
        w_restype = B_w_dynamic
    elif is_W_class(ret):
        w_restype = ret._w
    else:
        raise ValueError(f"Invalid return type: '{sig.return_annotation}'")

    return W_FuncType(func_params, w_restype)


def spy_builtin(qn: QN) -> Callable:
    """
    Decorator to make an interp-level function wrappable by the VM.

    Example of usage:

        @spy_builtin(QN("foo::hello"))
        def hello(vm: 'SPyVM', w_x: W_I32) -> W_Str:
            ...

        w_hello = vm.wrap(hello)
        assert isinstance(w_hello, W_BuiltinFunc)
        assert w_hello.qn == QN("foo::hello")

    The w_functype of the wrapped function is automatically computed by
    inspectng the signature of the interp-level function. The first parameter
    MUST be 'vm'.
    """
    def decorator(fn: Callable) -> Callable:
        w_functype = functype_from_sig(fn)
        fn._w = W_BuiltinFunc(w_functype, qn, fn)  # type: ignore
        fn.w_functype = w_functype  # type: ignore
        return fn
    return decorator
