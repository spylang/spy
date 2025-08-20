from typing import TYPE_CHECKING, Optional, Iterable
from spy.fqn import FQN
from spy.errors import WIP
from spy.vm.primitive import W_Dynamic
from spy.vm.b import B
from spy.vm.object import W_Object
from spy.vm.str import W_Str
from spy.vm.function import W_ASTFunc, W_Func
from spy.vm.builtin import builtin_method
from spy.vm.opspec import W_OpSpec, W_OpArg

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


ModItem = tuple[FQN, W_Object]


@B.builtin_type('module')
class W_Module(W_Object):
    vm: 'SPyVM'
    name: str
    filepath: Optional[str]
    _frozen: bool
    __spy_storage_category__ = 'reference'

    def __init__(self, vm: 'SPyVM', name: str, filepath: Optional[str]) -> None:
        self.vm = vm
        self.name = name # XXX should we kill name?
        self.fqn = FQN(name)
        self.filepath = filepath

    def __repr__(self) -> str:
        if self.filepath is None:
            return f'<spy module {self.name} (builtin)>'
        else:
            return f'<spy module {self.name}>'

    def is_builtin(self) -> bool:
        return self.filepath is None

    # ==== applevel interface =====

    @builtin_method('__getattribute__')
    @staticmethod
    def w_getattribute(vm: 'SPyVM', w_mod: 'W_Module',
                       w_attr: W_Str) -> W_Dynamic:
        attr = vm.unwrap_str(w_attr)
        return w_mod.getattr(attr)

    @builtin_method('__setattr__')
    @staticmethod
    def w_setattr(vm: 'SPyVM', w_mod: 'W_Module', w_attr:
                  W_Str, w_val: W_Dynamic) -> None:
        attr = vm.unwrap_str(w_attr)
        w_mod.setattr(attr, w_val)

    @builtin_method('__call_method__', color='blue', kind='metafunc')
    @staticmethod
    def w_CALL_METHOD(vm: 'SPyVM', wop_mod: W_OpArg, wop_name: W_OpArg,
                      *args_wop: W_OpArg) -> W_OpSpec:
        if wop_mod.color != 'blue':
            raise WIP('__call_method__ on red modules')

        w_mod = wop_mod.w_blueval
        assert isinstance(w_mod, W_Module)
        name = wop_name.blue_unwrap_str(vm)
        w_func = w_mod.getattr_maybe(name)
        if w_func is None:
            return W_OpSpec.NULL

        if isinstance(w_func, W_Func):
            return W_OpSpec(w_func, list(args_wop))
        else:
            raise WIP('trying to call a non-function (we should emit a better error)')


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
            if fqn.modname == self.name and len(fqn.parts) > 1:
                yield fqn

    def items_w(self) -> Iterable[ModItem]:
        for fqn, w_obj in self.vm.globals_w.items():
            if fqn.modname == self.name and len(fqn.parts) > 1:
                yield fqn, w_obj

    def pp(self) -> None:
        """
        Pretty print
        """
        print(f'Module {self.name}:')
        for attr, w_obj in self.items_w():
            print(f'    {attr}: {w_obj}')
