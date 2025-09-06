from typing import TYPE_CHECKING, Optional, Iterable
from spy.fqn import FQN
from spy.errors import WIP
from spy.vm.primitive import W_Dynamic
from spy.vm.b import B
from spy.vm.object import W_Object
from spy.vm.str import W_Str
from spy.vm.function import W_ASTFunc, W_Func
from spy.vm.builtin import builtin_method
from spy.vm.opspec import W_OpSpec, W_MetaArg

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

ModItem = tuple[FQN, W_Object]

# XXX the Cell type should not be on builtins
@B.builtin_type('Cell')
class W_Cell(W_Object):
    """
    XXX explain
    """

    def __init__(self, fqn: FQN, w_val: W_Object) -> None:
        self.fqn = fqn
        self._w_val = w_val

    def __repr__(self) -> str:
        return f'<spy cell {self.fqn} = {self._w_val}>'

    def get(self) -> W_Object:
        return self._w_val

    def set(self, w_val: W_Object) -> None:
        self._w_val = w_val


@B.builtin_type('module')
class W_Module(W_Object):
    vm: 'SPyVM'
    name: str
    filepath: Optional[str]
    _dict_w: dict[str, W_Object]
    _frozen: bool

    def __init__(self, vm: 'SPyVM', name: str, filepath: Optional[str]) -> None:
        self.vm = vm
        self.name = name # XXX should we kill name?
        self.fqn = FQN(name)
        self.filepath = filepath
        self._dict_w = {}

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
    def w_CALL_METHOD(vm: 'SPyVM', wam_mod: W_MetaArg, wam_name: W_MetaArg,
                      *args_wam: W_MetaArg) -> W_OpSpec:
        if wam_mod.color != 'blue':
            raise WIP('__call_method__ on red modules')

        w_mod = wam_mod.w_blueval
        assert isinstance(w_mod, W_Module)
        name = wam_name.blue_unwrap_str(vm)
        w_func = w_mod.getattr_maybe(name)
        if w_func is None:
            return W_OpSpec.NULL

        if isinstance(w_func, W_Func):
            return W_OpSpec(w_func, list(args_wam))
        else:
            raise WIP('trying to call a non-function (we should emit a better error)')


    # ==== public interp-level API ====

    def getattr_maybe(self, attr: str) -> Optional[W_Object]:
        return self._dict_w.get(attr)
        return w_res

    def getattr(self, attr: str) -> W_Object:
        return self._dict_w[attr]

    def setattr(self, attr: str, w_value: W_Object) -> None:
        self._dict_w[attr] = w_value

    def keys(self) -> Iterable[str]:
        return self._dict_w.keys()

    def items_w(self) -> Iterable[tuple[str, W_Object]]:
        return self._dict_w.items()

    # XXX: kill me
    def fqn_items_w(self) -> Iterable[ModItem]:
        raise NotImplementedError('use vm.fqns_by_modname')

    def pp(self) -> None:
        """
        Pretty print
        """
        print(f'Module {self.name}:')
        for attr, w_obj in self.fqn_items_w():
            print(f'    {attr}: {w_obj}')
