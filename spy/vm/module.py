from typing import TYPE_CHECKING, Optional, Iterable
from spy.fqn import FQN
from spy.vm.primitive import W_Dynamic, W_Void
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type
from spy.vm.str import W_Str
from spy.vm.function import W_ASTFunc
from spy.vm.builtin import builtin_func, builtin_method
from spy.vm.opimpl import W_OpImpl, W_OpArg

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM




@B.builtin_type('module')
class W_Module(W_Object):
    vm: 'SPyVM'
    name: str
    filepath: str
    _frozen: bool
    __spy_storage_category__ = 'reference'

    def __init__(self, vm: 'SPyVM', name: str, filepath: str) -> None:
        self.vm = vm
        self.name = name
        self.filepath = filepath

    def __repr__(self) -> str:
        return f'<spy module {self.name}>'

    # ==== operator impls =====

    @builtin_method('__GETATTR__', color='blue')
    @staticmethod
    def w_GETATTR(vm: 'SPyVM', wop_obj: W_OpArg, wop_attr: W_OpArg) -> W_OpImpl:
        """
        Ideally, we should create a new subtype for each module, where every
        member has its own static type.

        For now, we just use dynamic, which is good enough for now, since
        all the module getattrs are done in blue contexts are redshifted
        away.
        """
        @builtin_func('builtins', 'module_getattr')
        def w_fn(vm: 'SPyVM', w_mod: W_Module, w_attr: W_Str) -> W_Dynamic:
            attr = vm.unwrap_str(w_attr)
            return w_mod.getattr(attr)
        return W_OpImpl(w_fn)


    @builtin_method('__SETATTR__', color='blue')
    @staticmethod
    def w_SETATTR(vm: 'SPyVM', wop_obj: W_OpArg, wop_attr: W_OpArg,
                  wop_v: W_OpArg) -> W_OpImpl:
        @builtin_func('builtins', 'module_setattr')
        def w_fn(vm: 'SPyVM', w_mod: W_Module, w_attr:
                   W_Str, w_val: W_Dynamic) -> W_Void:
            attr = vm.unwrap_str(w_attr)
            w_mod.setattr(attr, w_val)
            return B.w_None
        return W_OpImpl(w_fn)

    # ==== public interp-level API ====

    def getattr_maybe(self, attr: str) -> Optional[W_Object]:
        fqn = FQN([self.name, attr])
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
        fqn = FQN([self.name, attr])
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
