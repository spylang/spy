from typing import Optional, TYPE_CHECKING
from spy.errors import SPyRuntimeError
from spy.vm.object import W_Object, W_Type, W_i32
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

class VarStorage:
    vm: 'SPyVM'
    name: str
    types_w: dict[str, W_Type]
    values_w: dict[str, Optional[W_Object]]

    def __init__(self, vm: 'SPyVM', name: str) -> None:
        self.vm = vm
        self.name = name
        self.types_w = {}
        self.values_w = {}

    def __repr__(self) -> str:
        return f'<VarStorage {self.name}>'

    def declare(self, name: str, w_type: W_Type) -> None:
        assert name not in self.types_w, f'variable already declared: {name}'
        self.types_w[name] = w_type
        self.values_w[name] = None # uninitialized

    def set(self, name: str, w_value: W_Object) -> None:
        # the invariant is that the produced bytecode should be type safe and
        # never try to set/get a variable with the wrong type. That's why we
        # have asserts instead of real exceptions.
        w_type = self.types_w[name]
        pyclass = self.vm.unwrap(w_type)
        assert isinstance(w_value, pyclass)
        self.values_w[name] = w_value

    def get(self, name: str) -> W_Object:
        assert name in self.types_w
        w_res = self.values_w[name]
        if w_res is None:
            raise SPyRuntimeError('read from uninitialized local')
        return w_res
