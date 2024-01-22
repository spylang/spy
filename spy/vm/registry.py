from typing import Callable, Optional, TYPE_CHECKING, Any
from dataclasses import dataclass
from spy.fqn import FQN
from spy.vm.function import W_FuncType, W_BuiltinFunc
from spy.vm.object import W_Object

class ModuleRegistry:
    """
    Keep track of all the objects which belong to a certain module.

    At startup, the `vm` will create a W_Module out of it.
    """
    modname: str
    filepath: str
    content: list[tuple[FQN, W_Object]]

    def __init__(self, modname: str, filepath: str) -> None:
        self.modname = modname
        self.filepath = filepath
        self.content = []

    if TYPE_CHECKING:
        def __getattr__(self, attr: str) -> Any:
            """
            Workaround for mypy blindness.

            When we do X.add('foo', ...), it becomes available as X.w_foo, but
            mypy obviously doesn't know. This is a big problem in particular
            for the B (builtins) module, since we use B.w_i32, B.w_object,
            etc. everywhere.

            By using this fake __getattr__, mypy will never complain about
            missing attributes on ModuleRegistry (which is a bit suboptimal,
            but well...)
            """

    def add(self, attr: str, w_obj: W_Object) -> None:
        fqn = FQN(modname=self.modname, attr=attr)
        setattr(self, f'w_{attr}', w_obj)
        self.content.append((fqn, w_obj))

    def primitive(self, sig: str, name: Optional[str] = None) -> Callable:
        w_functype = W_FuncType.parse(sig)

        def decorator(pyfunc: Callable) -> Callable:
            attr = name or pyfunc.__name__
            fqn = FQN(modname=self.modname, attr=attr)
            w_func = W_BuiltinFunc(w_functype, fqn, pyfunc)
            setattr(self, f'w_{attr}', w_func)
            self.content.append((fqn, w_func))
            return pyfunc

        return decorator
