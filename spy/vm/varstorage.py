from spy.vm.vm import SPyVM
from spy.vm.object import W_Object, W_Type, W_i32

class VarStorage:
    vm: SPyVM
    name: str
    types_w: dict[str, W_Type]
    values_w: dict[str, W_Object]

    def __init__(self, vm: SPyVM, name: str, types_w: dict[str, W_Type]) -> None:
        self.vm = vm
        self.name = name
        self.types_w = types_w
        self.values_w = {}
        for varname, w_type in types_w.items():
            # for now we know how to initialize only i32 local vars. We need
            # to think of a more generic way
            assert w_type is vm.builtins.w_i32
            self.values_w[varname] = W_i32(0)

    def __repr__(self) -> str:
        return f'<VarStorage {self.name}>'

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
        assert name in self.values_w
        return self.values_w[name]

    def add(self, name: str, w_value: W_Object) -> None:
        if name in self.values_w:
            raise Exception(f'Attribute {name} already present in the module')
        assert name not in self.types_w
        w_type = self.vm.dynamic_type(w_value)
        self.types_w[name] = w_type
        self.values_w[name] = w_value
