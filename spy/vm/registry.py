from typing import Callable, Optional
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

    def __init__(self, modname: str, filepath: str):
        self.modname = modname
        self.filepath = filepath
        self.content = []

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
