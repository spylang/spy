import py
from typing import Any, Optional, Iterable
import itertools
from dataclasses import dataclass
import fixedint
from spy.fqn import FQN
from spy import libspy
from spy.doppler import redshift
from spy.errors import SPyTypeError
from spy.vm.object import W_Object, W_Type, W_I32, W_F64
from spy.vm.str import W_Str
from spy.vm.b import B
from spy.vm.function import W_FuncType, W_Func, W_ASTFunc, W_BuiltinFunc
from spy.vm.module import W_Module
from spy.vm.registry import ModuleRegistry

from spy.vm.modules.builtins import BUILTINS
from spy.vm.modules.operator import OPERATOR

class SPyVM:
    """
    A Virtual Machine to execute SPy code.

    Each instance of the VM contains an instance of libspy.wasm: all the
    non-scalar objects (e.g. strings) are stored in the WASM linear memory.
    """
    ll: libspy.LLSPyInstance
    globals_types: dict[FQN, W_Type]
    globals_w: dict[FQN, W_Object]
    modules_w: dict[str, W_Module]
    unique_fqns: set[FQN]
    path: list[str]

    def __init__(self) -> None:
        self.ll = libspy.LLSPyInstance(libspy.LLMOD)
        self.globals_types = {}
        self.globals_w = {}
        self.modules_w = {}
        self.unique_fqns = set()
        self.path = []
        self.make_module(BUILTINS)  # builtins::
        self.make_module(OPERATOR)  # operator::

    def import_(self, modname: str) -> W_Module:
        from spy.irgen.irgen import make_w_mod_from_file
        if modname in self.modules_w:
            return self.modules_w[modname]
        # XXX for now we assume that we find the module as a single file in
        # the only vm.path entry. Eventually we will need a proper import
        # mechanism and support for packages
        assert self.path, 'vm.path not set'
        file_spy = py.path.local(self.path[0]).join(f'{modname}.spy')
        w_mod = make_w_mod_from_file(self, file_spy)
        self.modules_w[modname] = w_mod
        return w_mod

    def redshift(self) -> None:
        """
        Perform a redshift on all W_ASTFunc.
        """
        def should_redshift(w_func: W_ASTFunc) -> bool:
            # we don't want to redshift @blue functions
            return w_func.color != 'blue' and not w_func.redshifted

        def get_funcs() -> Iterable[tuple[FQN, W_ASTFunc]]:
            for fqn, w_func in self.globals_w.items():
                if isinstance(w_func, W_ASTFunc) and should_redshift(w_func):
                    yield fqn, w_func

        while True:
            funcs = list(get_funcs())
            if not funcs:
                break
            self._redshift_some(funcs)

    def _redshift_some(self, funcs: list[tuple[FQN, W_ASTFunc]]) -> None:
        for fqn, w_func in funcs:
            assert w_func.color != 'blue'
            assert not w_func.redshifted
            w_newfunc = redshift(self, w_func)
            assert w_newfunc.redshifted
            self.globals_w[fqn] = w_newfunc

    def register_module(self, w_mod: W_Module) -> None:
        assert w_mod.name not in self.modules_w
        self.modules_w[w_mod.name] = w_mod

    def make_module(self, reg: ModuleRegistry) -> None:
        w_mod = W_Module(self, reg.modname, reg.filepath)
        self.register_module(w_mod)
        for fqn, w_obj in reg.content:
            w_type = self.dynamic_type(w_obj)
            self.add_global(fqn, w_type, w_obj)

    def get_unique_FQN(self, *, modname: str, attr: str, is_global: bool) -> FQN:
        # if it's a global, we can create a "plain" FQN (e.g. `test::hello`)
        # which MUST be unique. If it's a closurwe, we attach a progressive ID
        # to create an unique FQN (e.g., `test::hello#42`)
        if is_global:
            fqn = FQN(modname=modname, attr=attr)
        else:
            # XXX this is potentially quadratic if we create tons of
            # conflicting FQNs, but for now we don't care
            for n in itertools.count():
                fqn = FQN(modname=modname, attr=attr, uniq_suffix=str(n))
                if fqn not in self.unique_fqns:
                    break
        assert fqn not in self.unique_fqns
        self.unique_fqns.add(fqn)
        return fqn

    def add_global(self,
                   fqn: FQN,
                   w_type: Optional[W_Type],
                   w_value: W_Object
                   ) -> None:
        assert fqn.modname in self.modules_w
        assert fqn not in self.globals_w
        assert fqn not in self.globals_types
        if w_type is None:
            w_type = self.dynamic_type(w_value)
        else:
            assert self.isinstance(w_value, w_type)
        self.globals_types[fqn] = w_type
        self.globals_w[fqn] = w_value

    def lookup_global_type(self, fqn: FQN) -> Optional[W_Type]:
        return self.globals_types.get(fqn)

    def lookup_global(self, fqn: FQN) -> Optional[W_Object]:
        return self.globals_w.get(fqn)

    def reverse_lookup_global(self, w_val: W_Object) -> Optional[FQN]:
        # XXX we should maintain a reverse-lookup table instead of doing a
        # linear search
        for fqn, w_obj in self.globals_w.items():
            if w_val is w_obj:
                return fqn
        return None

    def store_global(self, fqn: FQN, w_value: W_Object) -> None:
        w_type = self.globals_types[fqn]
        assert self.isinstance(w_value, w_type)
        self.globals_w[fqn] = w_value

    def dynamic_type(self, w_obj: W_Object) -> W_Type:
        assert isinstance(w_obj, W_Object)
        return w_obj.spy_get_w_type(self)

    def issubclass(self, w_sub: W_Type, w_super: W_Type) -> bool:
        assert isinstance(w_super, W_Type)
        assert isinstance(w_sub, W_Type)
        if w_super is B.w_dynamic:
            return True
        w_class = w_sub
        while w_class is not B.w_None:
            if w_class is w_super:
                return True
            w_class = w_class.w_base  # type:ignore
        return False

    def isinstance(self, w_obj: W_Object, w_type: W_Type) -> bool:
        w_t1 = self.dynamic_type(w_obj)
        return self.issubclass(w_t1, w_type)

    def typecheck(self, w_obj: W_Object, w_type: W_Type) -> None:
        """
        Like vm.isinstance(), but raise SPyTypeError if the check fails.
        """
        w_t1 = self.dynamic_type(w_obj)
        if not self.issubclass(w_t1, w_type):
            exp = w_type.name
            got = w_t1.name
            msg = f"Invalid cast. Expected `{exp}`, got `{got}`"
            raise SPyTypeError(msg)

    def is_True(self, w_obj: W_Object) -> bool:
        return w_obj is B.w_True

    def is_False(self, w_obj: W_Object) -> bool:
        return w_obj is B.w_False

    def wrap(self, value: Any) -> W_Object:
        """
        Useful for tests: magic funtion which wraps the given inter-level object
        into the most appropriate app-level W_* object.
        """
        T = type(value)
        if value is None:
            return B.w_None
        elif T in (int, fixedint.Int32):
            return W_I32(value)
        elif T is float:
            return W_F64(value)
        elif T is bool:
            if value:
                return B.w_True
            else:
                return B.w_False
        elif T is str:
            return W_Str(self, value)
        elif isinstance(value, type) and issubclass(value, W_Object):
            return value._w
        raise Exception(f"Cannot wrap interp-level objects " +
                        f"of type {value.__class__.__name__}")

    def unwrap(self, w_value: W_Object) -> Any:
        """
        Useful for tests: magic funtion which wraps the given app-level w_
        object into the most appropriate inter-level object. Opposite of
        wrap().
        """
        assert isinstance(w_value, W_Object)
        return w_value.spy_unwrap(self)

    def unwrap_i32(self, w_value: W_Object) -> Any:
        if not isinstance(w_value, W_I32):
            raise Exception('Type mismatch')
        return w_value.value

    def unwrap_f64(self, w_value: W_Object) -> Any:
        if not isinstance(w_value, W_F64):
            raise Exception('Type mismatch')
        return w_value.value

    def call_function(self, w_func: W_Func, args_w: list[W_Object]) -> W_Object:
        w_functype = w_func.w_functype
        assert w_functype.arity == len(args_w)
        for param, w_arg in zip(w_functype.params, args_w):
            self.typecheck(w_arg, param.w_type)
        #
        return w_func.spy_call(self, args_w)
