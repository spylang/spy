from typing import TYPE_CHECKING, Optional, Iterable
from spy.ast import FQN
from spy.vm.object import W_Object, spytype, W_Type
from spy.vm.varstorage import VarStorage
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM
    from spy.vm.function import W_UserFunction


@spytype('module')
class W_Module(W_Object):
    vm: 'SPyVM'
    name: str
    _frozen: bool

    def __init__(self, vm: 'SPyVM', name: str) -> None:
        self.vm = vm
        self.name = name

    def __repr__(self) -> str:
        return f'<spy module {self.name}>'

    def getattr_maybe(self, name: str) -> Optional[W_Object]:
        fqn = FQN.from_parts(self.name, name)
        return self.vm.lookup_global(fqn)

    def getattr(self, name: str) -> W_Object:
        w_obj = self.getattr_maybe(name)
        assert w_obj is not None
        return w_obj

    def getattr_userfunc(self, name: str) -> 'W_UserFunction':
        from spy.vm.function import W_UserFunction
        w_obj = self.getattr(w_obj)
        assert isinstance(w_obj, W_UserFunction)
        return w_obj

    def keys(self) -> Iterable[FQN]:
        for fqn in self.vm.globals_w.keys():
            if fqn.is_in_module(self.name):
                yield fqn

    def items_w(self) -> Iterable[W_Object]:
        for fqn, w_obj in self.vm.globals_w.items():
            if fqn.is_in_module(self.name):
                yield fqn, w_obj

    def pp(self) -> None:
        """
        Pretty print
        """
        from spy.vm.function import W_UserFunction
        print(f'Module {self.name}:')
        for attr, w_obj in self.items_w():
            print(f'    {attr}: {w_obj}')

        print()
        for attr, w_obj in self.items_w():
            if isinstance(w_obj, W_UserFunction):
                w_obj.w_code.pp()
