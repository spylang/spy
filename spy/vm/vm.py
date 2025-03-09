import py
from typing import Any, Optional, Iterable, Sequence
import itertools
from dataclasses import dataclass
from types import FunctionType
import fixedint
from spy.fqn import FQN
from spy.location import Loc
from spy import libspy
from spy.libspy import LLSPyInstance
from spy.doppler import redshift
from spy.errors import SPyTypeError
from spy.vm.object import W_Object, W_Type
from spy.vm.primitive import W_F64, W_I32, W_Bool, W_Dynamic
from spy.vm.str import W_Str
from spy.vm.list import W_ListType
from spy.vm.b import B
from spy.vm.function import W_FuncType, W_Func, W_ASTFunc, W_BuiltinFunc
from spy.vm.func_adapter import W_FuncAdapter
from spy.vm.module import W_Module
from spy.vm.opimpl import W_OpImpl, W_OpArg, w_oparg_eq
from spy.vm.registry import ModuleRegistry
from spy.vm.bluecache import BlueCache

from spy.vm.modules.builtins import BUILTINS
from spy.vm.modules.operator import OPERATOR
from spy.vm.modules.types import TYPES
from spy.vm.modules.unsafe import UNSAFE
from spy.vm.modules.rawbuffer import RAW_BUFFER
from spy.vm.modules.jsffi import JSFFI

# lazy definition of some some core types. See the docstring of W_Type.
W_Object._w.define(W_Object)
W_Type._w.define(W_Type)
W_OpImpl._w.define(W_OpImpl)
W_OpArg._w.define(W_OpArg)
W_FuncType._w.define(W_FuncType)

# W_OpImpl has w_meta_GETATTR, which means it creates a lazily-defined
# metaclass. Initialize it as well
W_OpImplType = type(W_OpImpl._w)
W_OpImplType._w.define(W_OpImplType)

class SPyVM:
    """
    A Virtual Machine to execute SPy code.

    Each instance of the VM contains an instance of libspy.wasm: all the
    non-scalar objects (e.g. strings) are stored in the WASM linear memory.
    """
    ll: LLSPyInstance
    globals_w: dict[FQN, W_Object]
    modules_w: dict[str, W_Module]
    path: list[str]
    bluecache: BlueCache

    def __init__(self, ll: Optional[LLSPyInstance]=None) -> None:
        if ll is None:
            assert libspy.LLMOD is not None
            self.ll = LLSPyInstance(libspy.LLMOD)
        else:
            self.ll = ll

        self.globals_w = {}
        self.modules_w = {}
        self.path = []
        self.bluecache = BlueCache(self)
        self.make_module(BUILTINS)   # builtins::
        self.make_module(OPERATOR)   # operator::
        self.make_module(TYPES)      # types::
        self.make_module(UNSAFE)     # unsafe::
        self.make_module(RAW_BUFFER) # rawbuffer::
        self.make_module(JSFFI)      # jsffi::


    @classmethod
    async def async_new(cls) -> 'SPyVM':
        """
        This is an alternative async ctor for SPyVM. It's needed for when
        we want to run spy under pyodide
        """
        llmod = await libspy.async_get_LLMOD()
        ll = await LLSPyInstance.async_new(llmod)
        return SPyVM(ll=ll)

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
        w_mod = W_Module(self, reg.fqn.modname, f'<reg.fqn.modname>')
        self.register_module(w_mod)
        for fqn, w_obj in reg.content:
            self.add_global(fqn, w_obj)

    def get_unique_FQN(self, fqn: FQN) -> FQN:
        """
        Get an unique variant of the given FQN, adding a suffix if necessary.
        """
        # XXX this is potentially quadratic if we create tons of
        # conflicting FQNs, but for now we don't care
        for n in itertools.count():
            fqn2 = fqn.with_suffix(n)
            if fqn2 not in self.globals_w:
                return fqn2
        assert False, 'unreachable'

    def add_global(self, fqn: FQN, w_value: W_Object) -> None:
        assert fqn.modname in self.modules_w
        w_existing = self.globals_w.get(fqn)
        if w_existing is None:
            self.globals_w[fqn] = w_value
        else:
            raise ValueError(f"'{fqn}' already exists")

    def lookup_global(self, fqn: FQN) -> Optional[W_Object]:
        if fqn.is_module():
            return self.modules_w.get(fqn.modname)
        else:
            return self.globals_w.get(fqn)

    def reverse_lookup_global(self, w_val: W_Object) -> Optional[FQN]:
        # XXX we should maintain a reverse-lookup table instead of doing a
        # linear search
        for fqn, w_obj in self.globals_w.items():
            if w_val == w_obj:
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
            # this is a W_ASTFunc which is NOT in the globals. The only
            # possibility is that it's a function which has already been
            # redshifted, in that case it is fine to return the FQN that we
            # already have
            w_func = self.lookup_global(w_val.fqn)
            assert isinstance(w_func, W_ASTFunc)
            assert w_func.redshifted
            return w_val.fqn
        elif isinstance(w_val, W_BuiltinFunc):
            # the fqn of builtin functions should be unique, else it's a fault
            # of whoever declared it.
            fqn = w_val.fqn
            assert w_val.fqn not in self.globals_w
        elif isinstance(w_val, W_Type):
            # for now types are only builtin so they must have an unique fqn,
            # we might need to change this when we introduce custom types
            fqn = w_val.fqn
            assert w_val.fqn not in self.globals_w
        else:
            assert False, 'implement me'

        assert fqn is not None
        self.add_global(fqn, w_val)
        return fqn

    def store_global(self, fqn: FQN, w_value: W_Object) -> None:
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
        return w_t1 == w_type or self.issubclass(w_t1, w_type)

    def typecheck(self, w_obj: W_Object, w_type: W_Type) -> None:
        """
        Like vm.isinstance(), but raise SPyTypeError if the check fails.
        """
        if not self.isinstance(w_obj, w_type):
            w_t1 = self.dynamic_type(w_obj)
            exp = w_type.fqn.human_name
            got = w_t1.fqn.human_name
            msg = f"Invalid cast. Expected `{exp}`, got `{got}`"
            raise SPyTypeError(msg)

    def is_type(self, w_obj: W_Object) -> bool:
        return self.isinstance(w_obj, B.w_type)

    def is_True(self, w_obj: W_Bool) -> bool:
        assert isinstance(w_obj, W_Bool)
        return w_obj is B.w_True

    def is_False(self, w_obj: W_Bool) -> bool:
        return w_obj is B.w_False

    def wrap(self, value: Any) -> W_Object:
        """
        Useful for tests: magic funtion which wraps the given interp-level
        object into the most appropriate app-level W_* object.
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
        elif isinstance(value, FunctionType):
            raise Exception(
                f"Cannot wrap interp-level function {value.__name__}. "
                f"Did you forget `@builtin_func`?")
        raise Exception(f"Cannot wrap interp-level objects " +
                        f"of type {value.__class__.__name__}")

    def unwrap(self, w_value: W_Object) -> Any:
        """
        Useful for tests: magic funtion which wraps the given app-level w_
        object into the most appropriate interp-level object. Opposite of
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

    def call(self, w_obj: W_Object, args_w: Sequence[W_Object]) -> W_Object:
        """
        The most generic way of calling an object.

        It calls OPERATOR.CALL in order to get an opimpl, then calls it.
        """
        raise NotImplementedError

    def fast_call(self, w_func: W_Func, args_w: Sequence[W_Object]) -> W_Object:
        """
        fast_call is a simpler calling convention which works only on
        W_Funcs.

        Arguments can be passed only positionally, and it assumes that types
        are correct.

        Blue functions are cached, as expected.
        """
        if w_func.color == 'blue' and not isinstance(w_func, W_FuncAdapter):
            # for blue functions, we memoize the result
            w_result = self.bluecache.lookup(w_func, args_w)
            if w_result is not None:
                return w_result
            w_result = self._raw_call(w_func, args_w)
            self.bluecache.record(w_func, args_w, w_result)
            return w_result
        else:
            # for red functions, we just call them
            return self._raw_call(w_func, args_w)

    def call_OP(self, w_OP: W_Func, args_wop: Sequence[W_OpArg]) -> W_Func:
        """
        Like vm.fast_call, but ensures that the result is a W_Func.

        Mostly useful to call OPERATORs.
        """
        # <TEMPORARY HACK>
        #
        # we don't want to over-specialize OPERATORs: for example, in case of
        # W_List.w_GETITEM(obj, i) we care only about the types, and we don't
        # care whether "i" is blue.
        #
        # args_wop contains W_OpArgs which directly comes from ASTFrame, and
        # so they might be either red or blue: e.g., if you do mylist[0], "0"
        # corresponds to a blue oparg. The idea is that we want to convert
        # "non-interesting" blue opargs into red opargs.

        # Ideally, each op_* should be able to specify whether it wants to
        # specialize only on types (i.e., red W_OpArgs) or also values (i.e.,
        # blue W_OpArgs). But we don't support that yet, so for now we use
        # some heuristics which seems to work:
        #
        #   1. for "single dispatch" operator, in which we have an "obj" which
        #      is the receiver of the OP, we keep it blue
        #
        #   2. for GETATTR, SETATTR, CALL_METHOD, we keep the attribute/method
        #      name blue
        #
        #   3. everything else becomes red
        OP = OPERATOR
        new_args_wop = [wop.as_red(self) for wop in args_wop]

        if w_OP in (OP.w_CALL, OP.w_CALL_METHOD, OP.w_GETATTR,
                    OP.w_GETITEM, OP.w_SETATTR, OP.w_SETITEM):
            new_args_wop[0] = args_wop[0]
        if w_OP in (OP.w_GETATTR, OP.w_SETATTR, OP.w_CALL_METHOD):
            new_args_wop[1] = args_wop[1]
        # </TEMPORARY HACK>

        w_func = self.fast_call(w_OP, new_args_wop)
        assert isinstance(w_func, W_Func)
        return w_func

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
        w_specialized = self.fast_call(w_func, generic_args_w)
        assert isinstance(w_specialized, W_Func)
        return self.fast_call(w_specialized, args_w)

    def _raw_call(self, w_func: W_Func,
                  args_w: Sequence[W_Object]) -> W_Object:
        """
        The most fundamental building block for calling in SPy.

        Like fast_call, but it doesn't handle blue caching. Never call this
        directly unless you know what you are doing.
        """
        w_functype = w_func.w_functype
        assert w_functype.is_argcount_ok(len(args_w))
        for param, w_arg in zip(w_functype.all_params(), args_w):
            assert self.isinstance(w_arg, param.w_type)
        return w_func.raw_call(self, args_w)

    def _w_oparg(self, w_x: W_Dynamic) -> W_OpArg:
        return W_OpArg(self, 'red', self.dynamic_type(w_x), None, Loc.here(-3))

    def eq(self, w_a: W_Dynamic, w_b: W_Dynamic) -> W_Bool:
        wop_a = self._w_oparg(w_a)
        wop_b = self._w_oparg(w_b)
        w_opimpl = self.call_OP(OPERATOR.w_EQ, [wop_a, wop_b])
        w_res = self.fast_call(w_opimpl, [w_a, w_b])
        assert isinstance(w_res, W_Bool)
        return w_res

    def ne(self, w_a: W_Dynamic, w_b: W_Dynamic) -> W_Bool:
        wop_a = self._w_oparg(w_a)
        wop_b = self._w_oparg(w_b)
        w_opimpl = self.call_OP(OPERATOR.w_NE, [wop_a, wop_b])
        w_res = self.fast_call(w_opimpl, [w_a, w_b])
        assert isinstance(w_res, W_Bool)
        return w_res

    def getitem(self, w_obj: W_Dynamic, w_i: W_Dynamic) -> W_Dynamic:
        # FIXME: we need a more structured way of implementing operators
        # inside the vm, and possibly share the code with typechecker and
        # ASTFrame. See also vm.ne and vm.getitem
        wop_obj = self._w_oparg(w_obj)
        wop_i = self._w_oparg(w_i)
        w_opimpl = self.call_OP(OPERATOR.w_GETITEM, [wop_obj, wop_i])
        return self.fast_call(w_opimpl, [w_obj, w_i])

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
            return self.fast_call(w_oparg_eq, [w_a, w_b])  # type: ignore

        wop_a = self._w_oparg(w_a)
        wop_b = self._w_oparg(w_b)
        try:
            w_opimpl = self.call_OP(OPERATOR.w_EQ, [wop_a, wop_b])
        except SPyTypeError:
            # sanity check: EQ between objects of the same type should always
            # be possible. If it's not, it means that we forgot to implement it
            w_ta = wop_a.w_static_type
            w_tb = wop_b.w_static_type
            assert w_ta is not w_tb, f'EQ missing on type `{w_ta.fqn}`'
            return B.w_False

        w_res = self.fast_call(w_opimpl, [w_a, w_b])
        assert isinstance(w_res, W_Bool)
        return w_res

    def universal_ne(self, w_a: W_Dynamic, w_b: W_Dynamic) -> W_Bool:
        return self.universal_eq(w_a, w_b).not_(self)

    def make_list_type(self, w_T: W_Type) -> W_ListType:
        w_res = self.getitem(B.w_list, w_T)
        assert isinstance(w_res, W_ListType)
        return w_res
