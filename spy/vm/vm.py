import py
from typing import Any, Optional, Iterable, Sequence
import itertools
from dataclasses import dataclass
from types import FunctionType
import fixedint
from spy.fqn import QN, FQN
from spy.location import Loc
from spy import libspy
from spy.doppler import redshift
from spy.errors import SPyTypeError
from spy.vm.object import W_Object, W_Type, W_I32, W_F64, W_Bool, W_Dynamic
from spy.vm.str import W_Str
from spy.vm.b import B
from spy.vm.sig import SPyBuiltin
from spy.vm.function import W_FuncType, W_Func, W_ASTFunc, W_BuiltinFunc
from spy.vm.module import W_Module
from spy.vm.opimpl import W_OpImpl, W_OpArg, oparg_eq
from spy.vm.registry import ModuleRegistry
from spy.vm.bluecache import BlueCache

from spy.vm.modules.builtins import BUILTINS
from spy.vm.modules.operator import OPERATOR
from spy.vm.modules.types import TYPES, W_TypeDef
from spy.vm.modules.unsafe import UNSAFE
from spy.vm.modules.rawbuffer import RAW_BUFFER
from spy.vm.modules.jsffi import JSFFI

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
    bluecache: BlueCache

    def __init__(self) -> None:
        self.ll = libspy.LLSPyInstance(libspy.LLMOD)
        self.globals_types = {}
        self.globals_w = {}
        self.modules_w = {}
        self.unique_fqns = set()
        self.path = []
        self.bluecache = BlueCache(self)
        self.make_module(BUILTINS)   # builtins::
        self.make_module(OPERATOR)   # operator::
        self.make_module(TYPES)      # types::
        self.make_module(UNSAFE)     # unsafe::
        self.make_module(RAW_BUFFER) # rawbuffer::
        self.make_module(JSFFI)      # jsffi::

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
        w_mod = W_Module(self, reg.qn.modname, reg.filepath)
        self.register_module(w_mod)
        for qn, w_obj in reg.content:
            fqn = self.get_FQN(qn, is_global=True)
            w_type = self.dynamic_type(w_obj)
            self.add_global(fqn, w_type, w_obj)

    def get_FQN(self, qn: QN, *, is_global: bool) -> FQN:
        """
        Get an unique FQN from a QN.

        Module-level names are considered "global": their FQN will get an
        empty suffix and must be unique. It is an error to try to "get_FQN()"
        the same global twice.

        For non globals (e.g., closures) the algorithm is simple: to compute
        an unique suffix, we just increment a numeric counter.
        """
        if is_global:
            fqn = FQN.make(qn, suffix="")
        else:
            # XXX this is potentially quadratic if we create tons of
            # conflicting FQNs, but for now we don't care
            for n in itertools.count():
                fqn = FQN.make(qn, suffix=str(n))
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
        assert isinstance(fqn, FQN)
        assert fqn.modname in self.modules_w or fqn.modname == '__fake_mod__'
        assert fqn not in self.globals_w
        assert fqn not in self.globals_types
        if w_type is None:
            w_type = self.dynamic_type(w_value)
        else:
            assert self.isinstance(w_value, w_type)
        self.globals_types[fqn] = w_type
        self.globals_w[fqn] = w_value

    def lookup_global_type(self, fqn: FQN) -> Optional[W_Type]:
        assert isinstance(fqn, FQN)
        return self.globals_types.get(fqn)

    def lookup_global(self, fqn: FQN) -> Optional[W_Object]:
        assert isinstance(fqn, FQN)
        if fqn.is_module():
            return self.modules_w.get(fqn.modname)
        else:
            return self.globals_w.get(fqn)

    def reverse_lookup_global(self, w_val: W_Object) -> Optional[FQN]:
        # XXX we should maintain a reverse-lookup table instead of doing a
        # linear search
        for fqn, w_obj in self.globals_w.items():
            if w_val is w_obj:
                return fqn
        return None

    def make_fqn_const(self, w_val: W_Object) -> FQN:
        """
        Check whether the given w_val has a corresponding FQN, and create
        one if needed.
        """
        fqn = self.reverse_lookup_global(w_val)
        if fqn is not None:
            return fqn

        # no FQN yet, we need to assign it one.
        if isinstance(w_val, W_ASTFunc):
            # it's a closure, let's assign it an FQN and add to the globals
            fqn = self.get_FQN(w_val.qn, is_global=False)
        elif isinstance(w_val, W_BuiltinFunc):
            # XXX open question: MUST builtin functions BE unique?
            # For "module-level" builtins it makes sense, and this call
            # used to pass "is_global=True", but e.g. list::eq is not
            # unique because list is a generic type. I think that the
            # solution is to introduce a more complex notion of
            # namespaces: currently it's just "modname::attr", but
            # probably we want to introduce at least
            # "modname::type::attr", or maybe even
            # "modname::namespace1::namespace2::...::attr".
            #
            # XXX temporary hack for list_eq, we should kill it eventually
            if w_val.qn.fullname == 'operator::list_eq':
                fqn = self.get_FQN(w_val.qn, is_global=False)
            else:
                fqn = self.get_FQN(w_val.qn, is_global=True)
        elif isinstance(w_val, W_Type):
            # this is terribly wrong: types should carry their own QN, as
            # functions do
            name = w_val.name.replace('[', '__').replace(']', '__')
            qn = QN(['__fake_mod__', name])
            fqn = self.get_FQN(qn, is_global=False)
        else:
            assert False, 'implement me'

        assert fqn is not None
        self.add_global(fqn, None, w_val)
        return fqn

    def store_global(self, fqn: FQN, w_value: W_Object) -> None:
        assert isinstance(fqn, FQN)
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
        #
        # XXX: these are needed to support automatic conversion from/to a
        # TypeDef and its origin type. For now it's fine, but eventually we
        # want to allow only explicit conversions. See
        # TestTypeDef.test_cast_from_to.
        if isinstance(w_sub, W_TypeDef):
            w_sub = w_sub.w_origintype
        if isinstance(w_super, W_TypeDef):
            w_super = w_super.w_origintype
        #
        w_class = w_sub
        while w_class is not B.w_None:
            if w_class is w_super:
                return True
            w_class = w_class.w_base  # type:ignore
        return False

    def union_type(self, w_t1: W_Type, w_t2: W_Type) -> W_Type:
        """
        Find the most precise common superclass of w_t1 and w_t2
        """
        if self.issubclass(w_t1, w_t2):
            return w_t2
        if self.issubclass(w_t2, w_t1):
            return w_t1
        #
        # w_base is either a type or B.w_None. Ideally, we would like to write:
        #     assert w_t1.w_base is not B.w_None
        # but in that case mypy cannot deduct that w_base IS actually a type.
        # The workaround is to check with isinstance
        assert isinstance(w_t1.w_base, W_Type)
        assert isinstance(w_t2.w_base, W_Type)
        return self.union_type(w_t1.w_base, w_t2.w_base)

    def isinstance(self, w_obj: W_Object, w_type: W_Type) -> bool:
        w_t1 = self.dynamic_type(w_obj)
        return self.issubclass(w_t1, w_type)

    def typecheck(self, w_obj: W_Object, w_type: W_Type) -> None:
        """
        Like vm.isinstance(), but raise SPyTypeError if the check fails.
        """
        w_t1 = self.dynamic_type(w_obj)
        if w_t1 != w_type and not self.issubclass(w_t1, w_type):
            exp = w_type.name
            got = w_t1.name
            msg = f"Invalid cast. Expected `{exp}`, got `{got}`"
            raise SPyTypeError(msg)

    def is_type(self, w_obj: W_Object) -> bool:
        return self.isinstance(w_obj, B.w_type)

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
        if isinstance(value, W_Object):
            return value
        elif value is None:
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
        elif isinstance(value, SPyBuiltin):
            return value._w
        elif isinstance(value, FunctionType):
            raise Exception(
                f"Cannot wrap interp-level function {value.__name__}. "
                f"Did you forget `@spy_builtin`?")
        raise Exception(f"Cannot wrap interp-level objects " +
                        f"of type {value.__class__.__name__}")

    def wrap_func(self, value: Any) -> W_Func:
        w_func = self.wrap(value)
        assert isinstance(w_func, W_Func)
        return w_func

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

    def unwrap_str(self, w_value: W_Object) -> str:
        if not isinstance(w_value, W_Str):
            raise Exception('Type mismatch')
        return self.unwrap(w_value) # type: ignore

    def call(self, w_func: W_Func, args_w: Sequence[W_Object]) -> W_Object:
        if w_func.color == 'blue':
            # for blue functions, we memoize the result
            w_result = self.bluecache.lookup(w_func, args_w)
            if w_result is not None:
                return w_result
            w_result = self._call_func(w_func, args_w)
            self.bluecache.record(w_func, args_w, w_result)
            return w_result
        else:
            # for red functions, we just call them
            return self._call_func(w_func, args_w)

    def call_OP(self, w_OP: W_Func, args_wop: Sequence[W_Object]) -> W_OpImpl:
        """
        Like vm.call, but ensures that the result is a W_OpImpl.

        Mostly useful to call OPERATORs.
        """
        w_opimpl = self.call(w_OP, args_wop)
        assert isinstance(w_opimpl, W_OpImpl)
        return w_opimpl

    def call_generic(self, w_func: W_Func,
                     generic_args_w: list[W_Object],
                     args_w: list[W_Object]) -> W_Object:
        """
        Shortcut to call generic functions.
            call_generic(f, [T0, T1], [a0, a1, a2])
        is more or less equivalent to:
            f_specialized = call(f, [T0, T1])
            call(f_specialized, [a0, a1, a2])
        """
        w_specialized = self.call(w_func, generic_args_w)
        assert isinstance(w_specialized, W_Func)
        return self.call(w_specialized, args_w)

    def _call_func(self, w_func: W_Func,
                   args_w: Sequence[W_Object]) -> W_Object:
        w_functype = w_func.w_functype
        assert w_functype.arity == len(args_w)
        for param, w_arg in zip(w_functype.params, args_w):
            self.typecheck(w_arg, param.w_type)
        return w_func.spy_call(self, args_w)

    def eq(self, w_a: W_Dynamic, w_b: W_Dynamic) -> W_Bool:
        wop_a = W_OpArg('a', 0, self.dynamic_type(w_a), Loc.here(-2))
        wop_b = W_OpArg('b', 1, self.dynamic_type(w_b), Loc.here(-2))
        w_opimpl = self.call_OP(OPERATOR.w_EQ, [wop_a, wop_b])
        w_res = w_opimpl.call(self, [w_a, w_b])
        assert isinstance(w_res, W_Bool)
        return w_res

    def ne(self, w_a: W_Dynamic, w_b: W_Dynamic) -> W_Bool:
        wop_a = W_OpArg('a', 0, self.dynamic_type(w_a), Loc.here(-2))
        wop_b = W_OpArg('b', 1, self.dynamic_type(w_b), Loc.here(-2))
        w_opimpl = self.call_OP(OPERATOR.w_NE, [wop_a, wop_b])
        w_res = w_opimpl.call(self, [w_a, w_b])
        assert isinstance(w_res, W_Bool)
        return w_res

    def getitem(self, w_obj: W_Dynamic, w_i: W_Dynamic) -> W_Dynamic:
        # FIXME: we need a more structured way of implementing operators
        # inside the vm, and possibly share the code with typechecker and
        # ASTFrame. See also vm.ne and vm.getitem
        wop_obj = W_OpArg('obj', 0, self.dynamic_type(w_obj), Loc.here(-2))
        wop_i = W_OpArg('i', 1, self.dynamic_type(w_i), Loc.here(-2))
        w_opimpl = self.call_OP(OPERATOR.w_GETITEM, [wop_obj, wop_i])
        return w_opimpl.call(self, [w_obj, w_i])

    def universal_eq(self, w_a: W_Dynamic, w_b: W_Dynamic) -> W_Bool:
        """
        Same as eq, but return False instead of TypeError in case the types are
        incompatible.

        This is meant to be useful e.g. for caching, where you want to be able
        to compare arbitrary objects, possibly of unrelated types.

        It's easier to understand the difference with some examples:

        a: i32 = 42
        b: str = 'hello'
        a == b                # TypeError: cannot do `i32` == `str`

        c: object = 42
        d: object = 'hello'
        c == d                # TypeError: cannot do `object` == `object`
        op.universal_eq(c, d) # False

        e: dynamic = 42
        f: dynamic = 'hello'
        e == f                # False, `dynamic` == `dynamic` => universal_eq
        op.universal_eq(e, f) # False

        Normally, the token "==" corresponds to op.EQ, so comparisons between
        unrelated types raises a TypeError. This means that `i32` == `str` is
        a compile-time error, which is what you would expect from a statically
        typed language.

        However, we treat "`dynamic` == `dynamic`" as a special case, and use
        op.UNIVERSAL_EQ instead. This is closer to the behavior that you have
        in Python, where "42 == 'hello'` is possible and returns False.
        """
        # Avoid infinite recursion:
        #   1. vm.universal_eq(a, t) calls
        #                    op.UNIVERSAL_EQ(W_OpArg(a, ...), W_OpArg(b, ...))
        #   2. UNIVERSAL_EQ is a blue function and thus uses BlueCache.lookup
        #   3. BlueCache.lookup calls vm.universal_eq on the W_OpArg
        #   4. vm.universal_eq(wop_a, wop_b) calls
        #                    op.UNIVERSAL_EQ(W_OpArg(...), W_OpArg(...))
        #   5  ...
        # By special-casing vm.universal_eq(W_OpArg, W_OpArg), we break the
        # recursion
        if isinstance(w_a, W_OpArg) and isinstance(w_b, W_OpArg):
            return oparg_eq(self, w_a, w_b)

        wop_a = W_OpArg('a', 0, self.dynamic_type(w_a), Loc.here(-2))
        wop_b = W_OpArg('b', 1, self.dynamic_type(w_b), Loc.here(-2))
        try:
            w_opimpl = self.call_OP(OPERATOR.w_EQ, [wop_a, wop_b])
        except SPyTypeError:
            # sanity check: EQ between objects of the same type should always
            # be possible. If it's not, it means that we forgot to implement it
            w_ta = wop_a.w_static_type
            w_tb = wop_b.w_static_type
            assert w_ta is not w_tb, f'EQ missing on type `{w_ta.name}`'
            return B.w_False

        w_res = w_opimpl.call(self, [w_a, w_b])
        assert isinstance(w_res, W_Bool)
        return w_res

    def universal_ne(self, w_a: W_Dynamic, w_b: W_Dynamic) -> W_Bool:
        return self.universal_eq(w_a, w_b).not_(self)

    def make_list_type(self, w_T: W_Type) -> W_Type:
        w_res = self.getitem(B.w_list, w_T)
        assert isinstance(w_res, W_Type)
        return w_res
