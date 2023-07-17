import typing
from spy.vm.object import W_Object, spytype
from spy.vm.varstorage import VarStorage
if typing.TYPE_CHECKING:
    from spy.vm.vm import SPyVM
    from spy.vm.function import W_Function

@spytype('module')
class W_Module(W_Object):
    vm: 'SPyVM'
    name: str
    content: VarStorage
    _frozen: bool

    def __init__(self, vm: 'SPyVM', name: str) -> None:
        self.vm = vm
        self.name = name
        self.content = VarStorage(vm, f"'{name} globals'", types_w={})
        self._frozen = False

    def __repr__(self) -> str:
        return f'<spy module {self.name}>'

    def freeze(self) -> None:
        self._frozen = True

    def add(self, name: str, w_value: W_Object) -> None:
        if self._frozen:
            raise Exception("Frozen")
        self.content.add(name, w_value)

    def getattr(self, name: str) -> W_Object:
        return self.content.get(name)

    def getattr_function(self, name: str) -> 'W_Function':
        from spy.vm.function import W_Function
        w_obj = self.content.get(name)
        assert isinstance(w_obj, W_Function)
        return w_obj

    def pp(self) -> None:
        """
        Pretty print
        """
        from spy.vm.function import W_Function
        print(f'Module {self.name}:')
        for attr, w_obj in self.content.values_w.items():
            print(f'    {attr}: {w_obj}')

        print()
        for attr, w_obj in self.content.values_w.items():
            if isinstance(w_obj, W_Function):
                w_obj.w_code.pp()
