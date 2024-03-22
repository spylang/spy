from typing import TYPE_CHECKING, Optional, Iterable
from spy.fqn import FQN
from spy.vm.object import W_Object, spytype, W_Type
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM
    from spy.vm.function import W_ASTFunc
    from spy.vm.str import W_Str


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

    # ==== operator impls =====

    def getattr_impl(self, vm: 'SPyVM', w_attr: 'W_Str') -> W_Object:
        # XXX this is wrong: ideally, we should create a new subtype for each
        # module, where every member has its own static type.
        #
        # For now, we just use dynamic, which is good enough for now, since
        # all the module getattrs are done in blue contexts are redshifted
        # away.
        attr = vm.unwrap_str(w_attr)
        return self.getattr(attr)

    def setattr_impl(self, vm: 'SPyVM', w_attr: 'W_Str',
                     w_val: 'W_Object') -> None:
        attr = vm.unwrap_str(w_attr)
        self.setattr(attr, w_val)

    # ==== public interp-level API ====

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

    def setattr(self, attr: str, w_value: W_Object) -> None:
        # XXX we should raise an exception if the attr doesn't exist
        fqn = FQN(modname=self.name, attr=attr)
        self.vm.store_global(fqn, w_value)

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
