from typing import Callable, Optional, TYPE_CHECKING, Any
from dataclasses import dataclass
from spy.fqn import QN
from spy.vm.function import W_FuncType, W_BuiltinFunc
from spy.vm.sig import spy_builtin
from spy.vm.object import W_Object

class ModuleRegistry:
    """
    Keep track of all the objects which belong to a certain module.

    At startup, the `vm` will create a W_Module out of it.
    """
    modname: str
    filepath: str
    content: list[tuple[QN, W_Object]]

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
        qn = QN(modname=self.modname, attr=attr)
        setattr(self, f'w_{attr}', w_obj)
        self.content.append((qn, w_obj))

    def builtin(self, pyfunc: Callable) -> Callable:
        attr = pyfunc.__name__
        qn = QN(modname=self.modname, attr=attr)
        # apply the @spy_builtin decorator to pyfunc
        spy_builtin(qn)(pyfunc)
        w_func = pyfunc._w  # type: ignore
        setattr(self, f'w_{attr}', w_func)
        self.content.append((qn, w_func))
        return pyfunc
