from typing import Optional, TYPE_CHECKING
from spy.location import Loc
from spy.errors import SPyRuntimeError, SPyTypeError
from spy.vm.object import W_Object, W_Type, W_i32
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

class VarStorage:
    vm: 'SPyVM'
    name: str
    types_w: dict[str, W_Type]
    values_w: dict[str, Optional[W_Object]]
    locs: dict[str, Loc]

    def __init__(self, vm: 'SPyVM', name: str) -> None:
        self.vm = vm
        self.name = name
        self.types_w = {}
        self.values_w = {}
        self.locs = {}

    def __repr__(self) -> str:
        return f'<VarStorage {self.name}>'

    def declare(self, loc: Loc, name: str, w_type: W_Type) -> None:
        assert name not in self.types_w, f'variable already declared: {name}'
        self.locs[name] = loc
        self.types_w[name] = w_type
        self.values_w[name] = None # uninitialized

    def set(self, loc: Loc, name: str, w_value: W_Object) -> None:
        self.typecheck(loc, name, w_value)
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

    def typecheck(self, got_loc: Loc, name: str, w_got: W_Object) -> None:
        # XXX: ideally, we should check the STATIC type of w_got, not the
        # dynamic type. But currently we are not keeping track of this info.
        w_type = self.types_w[name]
        if self.vm.is_compatible_type(w_got, w_type):
            return
        err = SPyTypeError('mismatched types')
        got = self.vm.dynamic_type(w_got).name
        exp = w_type.name
        exp_loc = self.locs[name]
        err.add('error', f'expected `{exp}`, got `{got}`', loc=got_loc)
        if name == '@return':
            because = 'because of return type'
        else:
            because = 'because of type declaration'
        err.add('note', f'expected `{exp}` {because}', loc=exp_loc)
        raise err
