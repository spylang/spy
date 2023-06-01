from spy.vm.vm import SPyVM
from spy.vm.object import W_Object, spytype
from spy.vm.varstorage import VarStorage

@spytype('module')
class W_Module(W_Object):
    vm: SPyVM
    name: str
    content: VarStorage
    _frozen: bool

    def __init__(self, vm: SPyVM, name: str) -> None:
        self.vm = vm
        self.name = name
        self.content = VarStorage(vm, f"'{name} globals'", types_w={})
        self._frozen = False

    def __repr__(self) -> str:
        return f'<spy module {self.name}>'

    def freeze(self):
        self._frozen = True

    def add(self, name: str, w_value: W_Object) -> None:
        if self._frozen:
            raise Exception("Frozen")
        self.content.add(name, w_value)
