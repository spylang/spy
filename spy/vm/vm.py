import itertools
from types import FunctionType
from typing import Any, Callable, Iterable, Optional, Sequence, Union, overload

import fixedint
import py.path

from spy import ROOT, ast, libspy
from spy.analyze.symtable import Color, ImportRef, maybe_blue
from spy.ast import Color, FuncKind
from spy.doppler import ErrorMode, redshift
from spy.errors import WIP, SPyError
from spy.fqn import FQN, QUALIFIERS
from spy.libspy import LLSPyInstance
from spy.location import Loc
from spy.util import func_equals
from spy.vm.b import B
from spy.vm.bluecache import BlueCache
from spy.vm.builtin import IRTag, make_builtin_func
from spy.vm.debugger import spdb
from spy.vm.exc import W_Exception, W_TypeError
from spy.vm.function import (
    CLOSURE,
    LocalVar,
    W_ASTFunc,
    W_BuiltinFunc,
    W_Func,
    W_FuncType,
)
from spy.vm.member import W_Member
from spy.vm.module import W_Module
from spy.vm.modules.__spy__ import SPY
from spy.vm.modules._testing_helpers import _TESTING_HELPERS
from spy.vm.modules.builtins import BUILTINS
from spy.vm.modules.jsffi import JSFFI
from spy.vm.modules.math import MATH
from spy.vm.modules.operator import OPERATOR
from spy.vm.modules.posix import POSIX
from spy.vm.modules.rawbuffer import RAW_BUFFER
from spy.vm.modules.time import TIME
from spy.vm.modules.types import TYPES, W_Loc
from spy.vm.modules.unsafe import UNSAFE
from spy.vm.object import W_Object, W_Type
from spy.vm.opimpl import W_OpImpl
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.primitive import (
    W_F64,
    W_I8,
    W_I32,
    W_U8,
    W_U32,
    W_Bool,
    W_Dynamic,
    W_NoneType,
    W_NotImplementedType,
    w_DynamicType,
)
from spy.vm.property import W_ClassMethod, W_Property, W_StaticMethod
from spy.vm.registry import ModuleRegistry
from spy.vm.str import W_Str
from spy.vm.struct import UnwrappedStruct

# lazy definition of some some core types. See the docstring of W_Type.
W_Object._w.define(W_Object)
W_Type._w.define(W_Type)
W_OpSpec._w.define(W_OpSpec)
W_MetaArg._w.define(W_MetaArg)
W_Property._w.define(W_Property)
W_StaticMethod._w.define(W_StaticMethod)
W_ClassMethod._w.define(W_ClassMethod)
W_Member._w.define(W_Member)
W_FuncType._w.define(W_FuncType)
W_I32._w.define(W_I32)
W_U32._w.define(W_U32)
W_I8._w.define(W_I8)
W_U8._w.define(W_U8)
W_F64._w.define(W_F64)
W_Bool._w.define(W_Bool)
W_NoneType._w.define(W_NoneType)
W_NotImplementedType._w.define(W_NotImplementedType)
W_Str._w.define(W_Str)
# note: W_Dynamic doesn't exist: the equivalent of W_Dynamic._w is
# w_DynamicType. See "The <dynamic> type" comment in primitive.py
w_DynamicType.define(W_Object)


STDLIB = ROOT.join("..", "stdlib")


class SPyVM:
    """
    A Virtual Machine to execute SPy code.

    Each instance of the VM contains an instance of libspy.wasm: all the
    non-scalar objects (e.g. strings) are stored in the WASM linear memory.
    """

    ll: LLSPyInstance
    globals_w: dict[FQN, W_Object]
    irtags: dict[FQN, IRTag]
    modules_w: dict[str, W_Module]
    path: list[str]
    bluecache: BlueCache
    emit_warning: Callable[[SPyError], None]
    # For use by --colorize to remember the red/blue color of each expr
    ast_color_map: Optional[dict[ast.Node, Color]]
    # If True, cache errors are collected and reported; if False, they're raised
    robust_import_caching: bool

    def __init__(self, ll: Optional[LLSPyInstance] = None) -> None:
        if ll is None:
            assert libspy.LLMOD is not None
            self.ll = LLSPyInstance(libspy.LLMOD)
        else:
            self.ll = ll

        self.globals_w = {}
        self.irtags = {}
        self.modules_w = {}
        self.path = [str(STDLIB)]
        self.bluecache = BlueCache(self)
        self.emit_warning = lambda err: None
        self.ast_color_map = None  # By default, don't keep track of expr colors.
        self.robust_import_caching = False  # By default, raise cache errors
        self.make_module(BUILTINS)
        self.make_module(OPERATOR)
        self.make_module(TYPES)
        self.make_module(MATH)
        self.make_module(UNSAFE)
        self.make_module(RAW_BUFFER)
        self.make_module(JSFFI)
        self.make_module(POSIX)
        self.make_module(TIME)
        self.make_module(SPY)
        self.make_module(_TESTING_HELPERS)
        self.call_INITs()

    @classmethod
    async def async_new(cls) -> "SPyVM":
        """
        This is an alternative async ctor for SPyVM. It's needed for when
        we want to run spy under pyodide
        """
        llmod = await libspy.async_get_LLMOD()
        ll = await LLSPyInstance.async_new(llmod)
        return SPyVM(ll=ll)

    def import_(self, modname: str) -> W_Module:
        from spy.analyze.importing import ImportAnalyzer

        if modname in self.modules_w:
            return self.modules_w[modname]

        importer = ImportAnalyzer(self, modname)
        importer.parse_all()
        # importer.pp()
        importer.import_all()
        w_mod = self.modules_w[modname]
        return w_mod

    def find_file_on_path(
        self, modname: str, allow_py_files: bool = False
    ) -> Optional[py.path.local]:
        # XXX for now we assume that we find the module as a single file in
        # the only vm.path entry. Eventually we will need a proper import
        # mechanism and support for packages
        assert self.path, "vm.path not set"
        for d in self.path:
            # XXX write test for this
            f = py.path.local(d).join(f"{modname}.spy")
            if f.exists():
                return f
            if allow_py_files:
                py_f = f.new(ext=".py")
                if py_f.exists():
                    return py_f

        return None

    def redshift(self, error_mode: ErrorMode) -> None:
        """
        Perform a redshift on all W_ASTFunc.
        """

        def should_redshift(w_func: W_ASTFunc) -> bool:
            # we don't want to redshift @blue functions
            return w_func.color != "blue" and not w_func.redshifted

        def get_funcs() -> Iterable[tuple[FQN, W_ASTFunc]]:
            for fqn, w_func in self.globals_w.items():
                if isinstance(w_func, W_ASTFunc) and should_redshift(w_func):
                    yield fqn, w_func

        while True:
            funcs = list(get_funcs())
            if not funcs:
                break
            self._redshift_some(funcs, error_mode)

    def _redshift_some(
        self,
        funcs: list[tuple[FQN, W_ASTFunc]],
        error_mode: ErrorMode,
    ) -> None:
        for fqn, w_func in funcs:
            assert w_func.color != "blue"
            assert not w_func.redshifted
            w_newfunc = redshift(self, w_func, error_mode)
            assert w_newfunc.redshifted
            self.globals_w[fqn] = w_newfunc

    def register_module(self, w_mod: W_Module) -> None:
        assert w_mod.name not in self.modules_w
        assert w_mod.fqn not in self.globals_w
        self.modules_w[w_mod.name] = w_mod
        self.globals_w[w_mod.fqn] = w_mod

    def make_module(self, reg: ModuleRegistry) -> None:
        w_mod = W_Module(reg.fqn.modname, None)
        self.register_module(w_mod)
        for fqn, w_obj in reg.content:
            # 1.register w_obj as a global constant
            self.add_global(fqn, w_obj)
            # 2. add it to the actual module
            assert len(fqn.parts) == 2
            assert fqn.modname == reg.fqn.modname
            name = fqn.symbol_name
            w_mod.setattr(name, w_obj)

    def call_INITs(self) -> None:
        for modname in self.modules_w:
            init_fqn = FQN(modname).join("__INIT__")
            w_init = self.globals_w.get(init_fqn)
            if w_init is not None:
                assert isinstance(w_init, W_Func)
                self.fast_call(w_init, [])

    def get_unique_FQN(self, fqn: FQN) -> FQN:
        """
        Get an unique variant of the given FQN, adding a suffix if necessary.
        """
        if fqn not in self.globals_w:
            # fqn not used yet, just return it
            return fqn

        # fqn already used, try to add an unique suffix.
        #
        # XXX this is potentially quadratic if we create tons of
        # conflicting FQNs, but for now we don't care
        for n in itertools.count(1):
            fqn2 = fqn.with_suffix(str(n))
            if fqn2 not in self.globals_w:
                return fqn2
        assert False, "unreachable"

    def lookup_ImportRef(self, impref: ImportRef) -> Optional[W_Object]:
        w_mod = self.modules_w.get(impref.modname)
        if impref.attr is None:
            return w_mod
        elif w_mod is not None:
            return w_mod.getattr_maybe(impref.attr)
        else:
            return None

    def add_global(
        self, fqn: FQN, w_value: W_Object, *, irtag: IRTag = IRTag.Empty
    ) -> None:
        assert fqn.modname in self.modules_w
        w_existing = self.globals_w.get(fqn)
        if w_existing is None:
            self.globals_w[fqn] = w_value
        else:
            raise ValueError(f"'{fqn}' already exists")
        self.irtags[fqn] = irtag

    def lookup_global_maybe(self, fqn: FQN) -> Optional[W_Object]:
        if fqn.is_module():
            return self.modules_w.get(fqn.modname)
        else:
            return self.globals_w.get(fqn)

    def lookup_global(self, fqn: FQN) -> W_Object:
        w_val = self.lookup_global_maybe(fqn)
        if w_val is None:
            raise Exception(f"lookup_global failed: {fqn}")
        return w_val

    def get_irtag(self, fqn: FQN) -> IRTag:
        return self.irtags.get(fqn, IRTag.Empty)

    def reverse_lookup_global(self, w_val: W_Object) -> Optional[FQN]:
        # XXX we should maintain a reverse-lookup table instead of doing a
        # linear search
        for fqn, w_obj in self.globals_w.items():
            if w_val == w_obj:
                return fqn
        return None

    def fqns_by_modname(self, modname: str) -> Iterable[tuple[FQN, W_Object]]:
        for fqn, w_obj in self.globals_w.items():
            if fqn.modname == modname and not fqn.is_module():
                yield (fqn, w_obj)

    def pp_globals(self, modname: Optional[str] = None) -> None:
        all_pbcs = sorted(
            self.globals_w.items(),
            key=lambda item: str(item[0]),  # item[0] is fqn
        )
        if modname is not None:
            all_pbcs = [
                (fqn, w_obj) for (fqn, w_obj) in all_pbcs if fqn.modname == modname
            ]

        last_modname = None
        for fqn, w_obj in all_pbcs:
            if fqn.modname != last_modname:
                print()
                print(f"{fqn.modname}::")
                last_modname = fqn.modname
            print(f"    {fqn}: {w_obj}")
        print()

    def pp_modules(self) -> None:
        for modname, w_mod in self.modules_w.items():
            w_mod.pp()
            print()

    def register_builtin_func(
        self,
        namespace: FQN | str,
        funcname: Optional[str] = None,
        qualifiers: QUALIFIERS = None,
        *,
        color: Color = "red",
        kind: FuncKind = "plain",
        extra_types: dict = {},
        irtag: IRTag = IRTag.Empty,
    ) -> Callable:
        """
        Decorator to turn an interp-level function into a W_BuiltinFunc.

        Example of usage:

            @vm.register_builtin_func("mymodule", "hello")
            def w_hello(vm: 'SPyVM', w_x: W_I32) -> W_Str:
                ...
            assert isinstance(w_hello, W_BuiltinFunc)
            assert w_hello.fqn == FQN("mymodule::hello")

        funcname can be omitted, and in that case it will automatically be
        deduced from __name__:

            @vm.register_builtin_func("mymodule")
            def w_hello(vm: 'SPyVM', w_x: W_I32) -> W_Str:
                ...
            assert w_hello.fqn == FQN("mymodule::hello")

        The w_functype of the wrapped function is automatically computed by
        inspectng the signature of the interp-level function. The first
        parameter MUST be 'vm'.

        Note that the resulting object is a W_BuiltinFunc, which means that you
        cannot call it directly, but you need to use vm.call.

        Registering a function with a FQN which is already in use is an
        error. Howver, it is explicitly allowed to register the SAME function
        with the SAME FQN multiple times. This is needed to allow this
        pattern:

            @MODULE.builtin_func
            def w_foo(vm: SPyVM):
                @vm.register_builtin_func(fqn)
                def w_bar(vm: SPyVM) -> W_Object:
                    ...

        Here, even if we call w_foo multiple times, we always end up with the
        "same" w_bar.  What "same function" means is not straightforward
        though, in particular in presence of closures. For that, we use
        spy.util.func_equals, which check function name, code objects and
        closed-over variables.
        """

        def decorator(fn: Callable) -> W_BuiltinFunc:
            # create the w_func
            w_func = make_builtin_func(
                fn,
                namespace,
                funcname,
                qualifiers,
                color=color,
                kind=kind,
                extra_types=extra_types,
            )

            # check whether the fqn is already in use
            w_other = self.lookup_global_maybe(w_func.fqn)
            if w_other is None:
                # fqn is free, register and return
                self.add_global(w_func.fqn, w_func, irtag=irtag)
                return w_func

            # the fqn is taken. Let's check that it's "the same". If any of
            # the following asserts fail, it probably means that we should
            # compute a better FQN which takes into account all the values
            # that it depends on.
            assert isinstance(w_other, W_BuiltinFunc)
            assert w_func.w_functype is w_other.w_functype
            assert w_func.fqn == w_other.fqn
            assert func_equals(w_func._pyfunc, w_other._pyfunc)

            # everything ok, we can just return the existing W_BuiltinFunc
            return w_other

        return decorator

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
            # ideally, I'd like ALL builtin funcs to be created with
            # @vm.register_builtin_func. This way, we should just assert that
            # w_val.fqn is already in vm.globals_w.
            #
            # However, this is not easily achievable at the moment, because we
            # create all module-level builtin functions AND all the
            # @builtin_method with make_builtin_func, bypassing the
            # @vm.register_builtin_func pass. This happens becuse we don't
            # have a vm available at that point, so it would require some
            # serious refactoring.
            fqn = w_val.fqn
            assert w_val.fqn not in self.globals_w

        elif isinstance(w_val, W_Type):
            # for now types are only builtin so they must have an unique fqn,
            # we might need to change this when we introduce custom types
            fqn = w_val.fqn
            assert w_val.fqn not in self.globals_w
        elif isinstance(w_val, W_Exception):
            # this is a bit of a temporary hack: it's needed to support this:
            #     raise Exception("...")

            # the argument to "raise" must be blue for now (see also
            # W_Exception.w_NEW). Eventually, we will have proper support
            # for prebuilt constants, but for now we special case W_Exception.
            w_T = self.dynamic_type(w_val)
            fqn = w_T.fqn.join("prebuilt")
            fqn = self.get_unique_FQN(fqn)
        else:
            w_T = self.dynamic_type(w_val)
            T = w_T.fqn.human_name
            msg = f"This prebuilt constant cannot be redshifted (yet): {w_val}"
            raise WIP(msg)
            assert False, "implement me"

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
            raise SPyError("W_TypeError", msg)

    def is_type(self, w_obj: W_Object) -> bool:
        return self.isinstance(w_obj, B.w_type)

    def is_True(self, w_obj: W_Bool) -> bool:
        assert isinstance(w_obj, W_Bool)
        return w_obj is B.w_True

    def is_False(self, w_obj: W_Bool) -> bool:
        return w_obj is B.w_False

    # ======== <vm.wrap typing> =========
    # The return type of vm.wrap depends on the type of the argument.
    #
    # The following series of @overload try to capture the runtime logic done
    # by vm.wrap. Note that bool, Int8, UInt8 etc are subclasses of int, so we
    # need extra care for that. In particular, we need to make sure that they
    # are listed *before* the overload wrap(int), and we need to ignore
    # overload-overlap.

    @overload
    def wrap(self, value: None) -> W_NoneType: ...

    @overload
    def wrap(self, value: bool) -> W_Bool: ...  # type: ignore[overload-overlap]

    @overload
    def wrap(self, value: fixedint.Int8) -> W_I8: ...  # type: ignore[overload-overlap]

    @overload
    def wrap(self, value: fixedint.UInt8) -> W_U8: ...  # type: ignore[overload-overlap]

    @overload
    def wrap(self, value: Union[fixedint.Int32, int]) -> W_I32: ...

    @overload
    def wrap(self, value: fixedint.UInt32) -> W_U32: ...  # type: ignore[overload-cannot-match]

    @overload
    def wrap(self, value: float) -> W_F64: ...

    @overload
    def wrap(self, value: str) -> W_Str: ...

    @overload
    def wrap(self, value: Any) -> W_Object: ...

    # ======== </vm.wrap typing> =========

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
        elif T is fixedint.UInt32:
            return W_U32(value)
        elif T is fixedint.Int8:
            return W_I8(value)
        elif T is fixedint.UInt8:
            return W_U8(value)
        elif T is float:
            return W_F64(value)
        elif T is bool:
            if value:
                return B.w_True
            else:
                return B.w_False
        elif T is str:
            return W_Str(self, value)
        elif T is Loc:
            return W_Loc(value)
        elif T is UnwrappedStruct:
            return value.spy_wrap(self)
        elif isinstance(value, FunctionType):
            raise Exception(
                f"Cannot wrap interp-level function {value.__name__}. "
                f"Did you forget `@builtin_func`?"
            )
        raise Exception(
            f"Cannot wrap interp-level objects " + f"of type {value.__class__.__name__}"
        )

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
            raise Exception("Type mismatch")
        return w_value.value

    def unwrap_u32(self, w_value: W_Object) -> Any:
        if not isinstance(w_value, W_U32):
            raise Exception("Type mismatch")
        return w_value.value

    def unwrap_i8(self, w_value: W_Object) -> Any:
        if not isinstance(w_value, W_I8):
            raise Exception("Type mismatch")
        return w_value.value

    def unwrap_u8(self, w_value: W_Object) -> Any:
        if not isinstance(w_value, W_U8):
            raise Exception("Type mismatch")
        return w_value.value

    def unwrap_f64(self, w_value: W_Object) -> Any:
        if not isinstance(w_value, W_F64):
            raise Exception("Type mismatch")
        return w_value.value

    def unwrap_str(self, w_value: W_Object) -> str:
        if not isinstance(w_value, W_Str):
            raise Exception("Type mismatch")
        return self.unwrap(w_value)  # type: ignore

    def unwrap_bool(self, w_value: W_Object) -> bool:
        if not isinstance(w_value, W_Bool):
            raise Exception("Type mismatch")
        return w_value.value

    def fast_call(self, w_func: W_Func, args_w: Sequence[W_Object]) -> W_Object:
        """
        fast_call is a simpler calling convention which works only on
        W_Funcs.

        Arguments can be passed only positionally, and it assumes that types
        are correct.

        Blue functions are cached, as expected.
        """
        if w_func.color == "blue":
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

    def fast_metacall(
        vm: "SPyVM", w_func: W_Func, args_wam: Sequence[W_MetaArg]
    ) -> W_OpSpec:
        """
        Return the OpSpec needed to call the given function.

        If w_func is a normal function --> OpSpec(w_func)

        If w_func is a metafunc, we call it and return whatever OpSpec it
        returns.
        """
        if w_func.w_functype.kind == "metafunc":
            w_res = vm.fast_call(w_func, args_wam)
            assert isinstance(w_res, W_OpSpec)
            return w_res
        else:
            return W_OpSpec(w_func, list(args_wam))

    def call_OP(
        self, loc: Optional[Loc], w_OP: W_Func, args_wam: Sequence[W_MetaArg]
    ) -> W_OpImpl:
        """
        Small wrapper around vm.fast_call, suited to call OPERATORs.

        `loc` points to the source code location which triggered the invocation of the
        operator. E.g., if we have `a + b`, it should point to ast.BinOp.loc.
        """
        try:
            w_opimpl = self.fast_call(w_OP, args_wam)
            assert isinstance(w_opimpl, W_OpImpl)
            return w_opimpl
        except SPyError as err:
            if loc is not None:
                opname = w_OP.fqn
                err.add("note", f"{opname} called here", loc)
            raise

    def call_generic(
        self, w_func: W_Func, generic_args_w: list[W_Object], args_w: list[W_Object]
    ) -> W_Object:
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

    def _raw_call(self, w_func: W_Func, args_w: Sequence[W_Object]) -> W_Object:
        """
        The most fundamental building block for calling in SPy.

        Like fast_call, but it doesn't handle blue caching. Never call this
        directly unless you know what you are doing.
        """
        w_functype = w_func.w_functype
        assert w_functype.is_argcount_ok(len(args_w))
        for param, w_arg in zip(w_functype.all_params(), args_w):
            assert self.isinstance(w_arg, param.w_T)
        return w_func.raw_call(self, args_w)

    def eval_opimpl(
        self,
        w_opimpl: W_OpImpl,
        args_wam: Sequence[W_MetaArg],
        *,
        loc: Loc,
        redshifting: bool = False,
    ) -> W_MetaArg:
        # hack hack hack
        # result color:
        #   - pure function and blue arguments -> blue
        #   - red function -> red
        #   - blue function -> blue
        w_functype = w_opimpl.w_functype
        color: Color
        if w_opimpl.is_pure():
            colors = [wam.color for wam in args_wam]
            color = maybe_blue(*colors)
        else:
            color = w_functype.color

        if color == "red" and redshifting:
            w_res = None
        else:
            args_w = [wam.w_val for wam in args_wam]
            w_res = w_opimpl._execute(self, args_w)

        return W_MetaArg(self, color, w_functype.w_restype, w_res, loc)

    # ======= operators ========
    #
    # For each operator "op" we have multiple versions:
    #
    #   - meta_op: do the metacall: operates on MetaArgs, return an OpImpl
    #   - op_wam: call meta_op, then execute the OpImpl. Operates on MetaArgs.
    #   - op_w: same as op_wam but operates on concrete W_Objects.

    def meta_eq(self, wam_a: W_MetaArg, wam_b: W_MetaArg, *, loc: Loc) -> W_OpImpl:
        return self.call_OP(loc, OPERATOR.w_EQ, [wam_a, wam_b])

    def eq_wam(self, wam_a: W_MetaArg, wam_b: W_MetaArg, *, loc: Loc) -> W_MetaArg:
        w_opimpl = self.meta_eq(wam_a, wam_b, loc=loc)
        return self.eval_opimpl(w_opimpl, [wam_a, wam_b], loc=loc)

    def eq_w(
        self, w_a: W_Dynamic, w_b: W_Dynamic, *, loc: Optional[Loc] = None
    ) -> W_Bool:
        wam_a = W_MetaArg.from_w_obj(self, w_a)
        wam_b = W_MetaArg.from_w_obj(self, w_b)
        wam = self.eq_wam(wam_a, wam_b, loc=loc or Loc.here(-2))
        assert isinstance(wam.w_val, W_Bool)
        return wam.w_val

    def meta_ne(self, wam_a: W_MetaArg, wam_b: W_MetaArg, *, loc: Loc) -> W_OpImpl:
        "a != b (metacall)"
        return self.call_OP(loc, OPERATOR.w_NE, [wam_a, wam_b])

    def ne_wam(self, wam_a: W_MetaArg, wam_b: W_MetaArg, *, loc: Loc) -> W_MetaArg:
        "a != b (on meta arguments)"
        w_opimpl = self.meta_ne(wam_a, wam_b, loc=loc)
        return self.eval_opimpl(w_opimpl, [wam_a, wam_b], loc=loc)

    def ne_w(
        self, w_a: W_Dynamic, w_b: W_Dynamic, *, loc: Optional[Loc] = None
    ) -> W_Bool:
        "a != b (dynamic dispatch)"
        wam_a = W_MetaArg.from_w_obj(self, w_a)
        wam_b = W_MetaArg.from_w_obj(self, w_b)
        wam = self.ne_wam(wam_a, wam_b, loc=loc or Loc.here(-2))
        assert isinstance(wam.w_val, W_Bool)
        return wam.w_val

    def meta_getitem(self, wam_o: W_MetaArg, wam_i: W_MetaArg, *, loc: Loc) -> W_OpImpl:
        "o[i] (metacall)"
        return self.call_OP(loc, OPERATOR.w_GETITEM, [wam_o, wam_i])

    def getitem_wam(self, wam_o: W_MetaArg, wam_i: W_MetaArg, *, loc: Loc) -> W_MetaArg:
        "o[i] (on meta arguments)"
        w_opimpl = self.meta_getitem(wam_o, wam_i, loc=loc)
        return self.eval_opimpl(w_opimpl, [wam_o, wam_i], loc=loc)

    def getitem_w(
        self,
        w_o: W_Dynamic,
        w_i: W_Dynamic,
        *,
        loc: Optional[Loc] = None,
        color: Color = "blue",
    ) -> W_Dynamic:
        "o[i] (dynamic dispatch)"
        wam_o = W_MetaArg.from_w_obj(self, w_o, color=color)
        wam_i = W_MetaArg.from_w_obj(self, w_i, color=color)
        wam = self.getitem_wam(wam_o, wam_i, loc=loc or Loc.here(-2))
        return wam.w_val

    def meta_call(
        self, wam_func: W_MetaArg, args_wam: list[W_MetaArg], *, loc: Loc
    ) -> W_OpImpl:
        "func(*args) (metacall)"
        return self.call_OP(loc, OPERATOR.w_CALL, [wam_func] + args_wam)

    def call_wam(
        self, wam_func: W_MetaArg, args_wam: list[W_MetaArg], *, loc: Loc
    ) -> W_MetaArg:
        "func(*args) (on meta arguments)"
        w_opimpl = self.meta_call(wam_func, args_wam, loc=loc)
        return self.eval_opimpl(w_opimpl, [wam_func] + args_wam, loc=loc)

    def call_w(
        self,
        w_func: W_Dynamic,
        args_w: Sequence[W_Dynamic],
        *,
        loc: Optional[Loc] = None,
        color: Color = "blue",
    ) -> W_Dynamic:
        "func(*args) (dynamic dispatch)"
        wam_func = W_MetaArg.from_w_obj(self, w_func)
        args_wam = [W_MetaArg.from_w_obj(self, w_arg, color=color) for w_arg in args_w]
        wam = self.call_wam(wam_func, args_wam, loc=loc or Loc.here(-2))
        return wam.w_val

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
        wam_a = W_MetaArg.from_w_obj(self, w_a)
        wam_b = W_MetaArg.from_w_obj(self, w_b)
        try:
            w_opimpl = self.call_OP(None, OPERATOR.w_EQ, [wam_a, wam_b])
        except SPyError as err:
            if not err.match(W_TypeError):
                raise
            # sanity check: EQ between objects of the same type should always
            # be possible. If it's not, it means that we forgot to implement it
            w_ta = wam_a.w_static_T
            w_tb = wam_b.w_static_T
            assert w_ta is not w_tb, f"EQ missing on type `{w_ta.fqn}`"
            return B.w_False

        wam_res = self.eval_opimpl(w_opimpl, [wam_a, wam_b], loc=Loc.here())
        w_res = wam_res.w_val
        assert isinstance(w_res, W_Bool)
        return w_res

    def universal_ne(self, w_a: W_Dynamic, w_b: W_Dynamic) -> W_Bool:
        return self.universal_eq(w_a, w_b).not_(self)

    def str_wam(self, wam_obj: W_MetaArg, *, loc: Loc) -> W_MetaArg:
        "str(obj) (on meta arguments)"
        wam_str = W_MetaArg.from_w_obj(self, B.w_str)
        return self.call_wam(wam_str, [wam_obj], loc=loc)

    def str_w(self, w_obj: W_Dynamic, *, loc: Optional[Loc] = None) -> W_Dynamic:
        "str(obj) (dynamic dispatch)"
        return self.call_w(B.w_str, [w_obj], loc=loc or Loc.here(-2))

    def repr_wam(self, wam_o: W_MetaArg, *, loc: Loc) -> W_MetaArg:
        "repr(obj) (on meta arguments)"
        wam_repr = W_MetaArg.from_w_obj(self, BUILTINS.w_repr)
        return self.call_wam(wam_repr, [wam_o], loc=loc)
