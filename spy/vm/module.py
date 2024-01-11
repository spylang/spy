from typing import TYPE_CHECKING, Optional, Iterable
from spy.fqn import FQN
from spy.vm.object import W_Object, spytype, W_Type
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM
    from spy.vm.function import W_ASTFunc


@spytype('module')
class W_Module(W_Object):
    vm: 'SPyVM'
    name: str
    filepath: str
    _frozen: bool

    def __init__(self, vm: 'SPyVM', name: str, filepath: str) -> None:
        self.vm = vm
        self.name = name
        self.filepath = filepath

    def __repr__(self) -> str:
        return f'<spy module {self.name}>'

    def getattr_maybe(self, attr: str) -> Optional[W_Object]:
        fqn = FQN(modname=self.name, attr=attr)
        return self.vm.lookup_global(fqn)

    def getattr(self, attr: str) -> W_Object:
        w_obj = self.getattr_maybe(attr)
        assert w_obj is not None
        return w_obj

    def getattr_astfunc(self, attr: str) -> 'W_ASTFunc':
        from spy.vm.function import W_ASTFunc
        w_obj = self.getattr(attr)
        assert isinstance(w_obj, W_ASTFunc)
        return w_obj

    def keys(self) -> Iterable[FQN]:
        for fqn in self.vm.globals_w.keys():
            if fqn.modname == self.name:
                yield fqn

    def items_w(self) -> Iterable[tuple[FQN, W_Object]]:
        for fqn, w_obj in self.vm.globals_w.items():
            if fqn.modname == self.name:
                yield fqn, w_obj

    def pp(self) -> None:
        """
        Pretty print
        """
        print(f'Module {self.name}:')
        for attr, w_obj in self.items_w():
            print(f'    {attr}: {w_obj}')
