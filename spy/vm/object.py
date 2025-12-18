"""
==================================
Terminology and naming conventions
==================================

SPy is implemented in Python. Many concepts such as classes, objects,
variables, etc. exist in both langauges, so we need a way to refer to them and
avoid confusion:

  - "application level"  or "app-level" refers to the code written by the final
    user and contained inside *.spy files;

  - "interpreter level"  or "interp-level" refers to the implementation of SPy,
    written by us, and contained inside *.py files.

In interp-level code, variables and fields which contains references to
app-level objects are always prefixed with w_, which stans for "wrapped":
e.g., the app-level SPy object `100` is represented by the interp-level
instance `W_I32(100)`, which is a wrapper around the interp-level object `100`.

=================
SPy object model
=================

The SPy object model is modeled against the Python one, which itself derives
from ObjVlisp: <object> and <type> are the two bottom types and are
intertwined:

  - <object> is the base class for everything
  - <type> is a subclass of <object>
  - <type> is the metaclass of <object>
  - <type> is the metaclass of itself

The following page contains a nice explanation:
https://aosabook.org/en/500L/a-simple-object-model.html

SPy builtin app-level types are implemented as interp-level Python classes,
whose name starts with the W_ prefix. The root of the object hierarchy is
W_Object.

SPy app-level objects are interp-level instances of those classes.

For simple cases, SPy app-level types are instances of W_Type, which is
basically a thin wrapper around the correspindig interp-level W_* class.
"""

import typing
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Callable,
    ClassVar,
    Literal,
    Optional,
    Self,
    Sequence,
    Type,
    Union,
)

from spy.ast import Color
from spy.errors import WIP, SPyError
from spy.fqn import FQN
from spy.vm.b import B

if TYPE_CHECKING:
    from spy.vm.builtin import FuncKind
    from spy.vm.field import W_Field
    from spy.vm.function import W_Func
    from spy.vm.opspec import W_MetaArg, W_OpSpec
    from spy.vm.primitive import W_Bool, W_NoneType
    from spy.vm.vm import SPyVM


def builtin_method(
    name: str, *, color: Color = "red", kind: "FuncKind" = "plain"
) -> Any:
    """
    Turn an interp-level method into an app-level one.

    This decorator just puts a mark on the function, the actual job is done by
    W_Type._init_builtin_method().
    """

    def decorator(fn: Callable) -> Callable:
        assert isinstance(fn, staticmethod), "missing @staticmethod"
        fn.spy_builtin_method = (name, color, kind, "method")  # type: ignore
        return fn

    return decorator


def builtin_staticmethod(
    name: str, *, color: Color = "red", kind: "FuncKind" = "plain"
) -> Any:
    """
    Turn an interp-level staticmethod into an app-level staticmethod.

    This decorator just puts a mark on the function, the actual job is done by
    W_Type._init_builtin_method().
    """

    def decorator(fn: Callable) -> Callable:
        assert isinstance(fn, staticmethod), "missing @staticmethod"
        fn.spy_builtin_method = (name, color, kind, "staticmethod")  # type: ignore
        return fn

    return decorator


def builtin_classmethod(
    name: str, *, color: Color = "red", kind: "FuncKind" = "plain"
) -> Any:
    """
    Turn an interp-level staticmethod into an app-level classmethod.

    This decorator just puts a mark on the function, the actual job is done by
    W_Type._init_builtin_method().
    """

    def decorator(fn: Callable) -> Callable:
        assert isinstance(fn, staticmethod), "missing @staticmethod"
        fn.spy_builtin_method = (name, color, kind, "classmethod")  # type: ignore
        return fn

    return decorator


def builtin_property(
    name: str, *, color: Color = "red", kind: "FuncKind" = "plain"
) -> Any:
    """
    Turn an interp-level getter method into an app-level property.

    This decorator just puts a mark on the function, the actual job is done by
    W_Type._init_builtin_method().
    """

    def decorator(fn: Callable) -> Callable:
        assert isinstance(fn, staticmethod), "missing @staticmethod"
        fn.spy_builtin_method = (name, color, kind, "property")  # type: ignore
        return fn

    return decorator


class builtin_class_attr:
    """
    Turn an interp-level class attribute into an app-level one.

    See test_builtin.py::test_builtin_class_attr for usage.
    """

    def __init__(self, name: str, w_val: "W_Object") -> None:
        self.name = name
        self.w_val = w_val

    def __repr__(self) -> str:
        return f"<builtin_class_attr '{self.name}' = {self.w_val}>"

    def __get__(self, instance: Any, owner: type) -> "W_Object":
        return self.w_val


# Basic setup of the object model: <object> and <type>
# =====================================================

# NOTE: contrarily to all the other builtin types, for W_Object and W_Type we
# cannot use @B.builtin_type, because of bootstrapping issues.  See also the
# section "Initial setup of the 'builtins' module"


class W_Object:
    """
    The root of SPy object hierarchy
    """

    _w: ClassVar["W_Type"]  # set by @builtin_type

    # Storage category:
    #   - 'value': compares by value, don't have an identity, 'is' is
    #     forbidden. E.g., i32, f64, str.
    #   - 'reference': compare by identity
    __spy_storage_category__ = "reference"

    def __repr__(self) -> str:
        fqn = self._w.fqn
        addr = f"0x{id(self):x}"
        return f"<spy instance: type={fqn.human_name}, id={addr}>"

    def spy_get_w_type(self, vm: "SPyVM") -> "W_Type":
        pyclass = type(self)
        T = pyclass.__name__
        _w = pyclass.__dict__.get("_w")
        assert _w is not None, f"class {T} misses @builtin_type"
        return pyclass._w

    def spy_unwrap(self, vm: "SPyVM") -> Any:
        spy_type = vm.dynamic_type(self).fqn
        py_type = self.__class__.__name__
        raise Exception(
            f"Cannot unwrap app-level objects of type {spy_type} "
            f"(interp-level type: {py_type})"
        )

    def spy_key(self, vm: "SPyVM") -> Any:
        """
        Return an interp-level object which can be used as a key for an
        inter-level dict.

        The main use case is to record BlueCache entries: so object which is
        passed as blue argument must implement it.

        The default implementation works only if __spy_storage_category__ ==
        'reference', and compares/hashes by identity.

        Subclasses setting __spy_storage_category__ == 'value' must override
        this method.
        """
        assert self.__spy_storage_category__ == "reference"
        return self  # rely on Python's default __hash__ and __eq__

    def spy_dir(self, vm: "SPyVM") -> set[str]:
        return set()

    @builtin_method("__repr__", color="blue", kind="metafunc")
    @staticmethod
    def w_REPR(vm: "SPyVM", wam_self: "W_MetaArg") -> "W_OpSpec":
        from spy.vm.builtin import IRTag
        from spy.vm.opspec import W_OpSpec
        from spy.vm.str import W_Str

        if wam_self.color == "blue":
            w_self = wam_self.w_blueval
            w_s = vm.wrap(repr(w_self))
            return W_OpSpec.const(w_s)

        else:
            # fallback
            w_T = wam_self.w_static_T
            T = Annotated[W_Object, w_T]
            irtag = IRTag("object.repr", w_T=w_T)

            @vm.register_builtin_func(w_T.fqn, "__generic_repr__", irtag=irtag)
            def w_generic_repr(vm: "SPyVM", w_obj: T) -> W_Str:
                tname = w_T.fqn.human_name
                addr = f"0x{id(w_obj):x}"
                s = f"<spy `{tname}` object at {addr}>"
                return vm.wrap(s)

            return W_OpSpec(w_generic_repr, [wam_self])

    @builtin_method("__str__", color="blue", kind="metafunc")
    @staticmethod
    def w_STR(vm: "SPyVM", wam_self: "W_MetaArg") -> "W_OpSpec":
        # default implementation: fallback to __repr__
        w_T = wam_self.w_static_T
        if w_repr := w_T.lookup_func("__repr__"):
            return vm.fast_metacall(w_repr, [wam_self])

        # this should never happen since we define __repr__ on W_Object
        from spy.vm.opspec import W_OpSpec

        return W_OpSpec.NULL

    # ==== OPERATOR SUPPORT ====
    #
    # Operators are the central concept which drives the semantic of SPy
    # objects, because they map syntactic constructs into runtime behavior.
    #
    # There is a 1:1 mapping between syntax and its corresponding function in
    # the `operator` module. For example:
    #
    #     a + b ==> operator.add(a, b)
    #     a.b   ==> operator.getattr(a, "b")
    #
    # Types can implement each operator by implementing __special__ methods
    # such as `__add__` or `__getattribute__`.
    #
    # __special__ methods can be defined as normal functions and executed as
    # expected.
    #
    # Additionally, __special__ methods can be defined as *metafunctions*. In
    # that case, they obey to the standard three-phase metacall protocol:
    #
    #   1. [blue] metacall: invoke the metafunction, which returns an OpSpec
    #   2. [blue] typecheck: the OpSpec is typechecked and turned into an OpImpl
    #   3. [red]  execution: the OpImpl is executed
    #
    # Metafunctions don't receive the concrete values, but receive abstract
    # MetaArgs, which carry the static_type, the color, the definition location,
    # etc.
    #
    # For example, consider the following expression:
    #     return obj.a
    #
    # If __getattribute__ is a metafunction, this is more or less what happens:
    #
    #     T = STATIC_TYPE(obj)
    #     m_obj = MetaArg('red', T, ...)
    #     m_attr = MetaArg('blue', str, "a")
    #     opimpl = operator.GETATTR(m_obj, m_attr)
    #     opimpl.execute(obj)
    #
    # The actual logic for the SPy VM resides in the 'operator' module (see
    # spy/vm/modules/operator).
    #
    # Subclasses of W_Object can implement their own __special__ methods in
    # this way:
    #
    # class W_Myclass(W_Object):
    #
    #     # implement __getitem__ as a normal function
    #     @builtin_method('__getitem__')
    #     @staticmethod
    #     def w_getitem(vm: 'SPyVM', w_self: 'W_MyClass', w_i: W_I32) -> W_I32:
    #         ...
    #
    #     # implement __getattribute__ as a metafunc
    #     @builtin_method('__getattribute__', color='blue', kind='metafunc')
    #     def w_GETATTRIBUTE(vm: 'SPyVM', wam_self: W_MetaArg,
    #                        wam_name: W_MetaArg) -> W_OpSpec:
    #         ...
    #
    # The naming convention at interp-level is the following:
    #   - for normal functions, we use w_getitem, w_getattribute, etc.
    #   - for meta functions, we use w_GETITEM, w_GETATTRIBUTE, etc.
    #
    # The following declarations are not strictly needed, but they are
    # provided so that in case a subclass decides to override them, mypy can
    # check the signatures

    @staticmethod
    def w_EQ(vm: "SPyVM", wam_a: "W_MetaArg", wam_b: "W_MetaArg") -> "W_OpSpec":
        raise NotImplementedError("this should never be called")

    @staticmethod
    def w_NE(vm: "SPyVM", wam_a: "W_MetaArg", wam_b: "W_MetaArg") -> "W_OpSpec":
        raise NotImplementedError("this should never be called")

    @staticmethod
    def w_GETATTRIBUTE(
        vm: "SPyVM", wam_obj: "W_MetaArg", wam_name: "W_MetaArg"
    ) -> "W_OpSpec":
        raise NotImplementedError("this should never be called")

    @staticmethod
    def w_SETATTR(
        vm: "SPyVM", wam_obj: "W_MetaArg", wam_name: "W_MetaArg", wam_v: "W_MetaArg"
    ) -> "W_OpSpec":
        raise NotImplementedError("this should never be called")

    @staticmethod
    def w_GETITEM(vm: "SPyVM", wam_obj: "W_MetaArg", wam_i: "W_MetaArg") -> "W_OpSpec":
        raise NotImplementedError("this should never be called")

    @staticmethod
    def w_SETITEM(
        vm: "SPyVM", wam_obj: "W_MetaArg", wam_i: "W_MetaArg", wam_v: "W_MetaArg"
    ) -> "W_OpSpec":
        raise NotImplementedError("this should never be called")

    @staticmethod
    def w_CALL(vm: "SPyVM", wam_obj: "W_MetaArg", *args_wam: "W_MetaArg") -> "W_OpSpec":
        raise NotImplementedError("this should never be called")

    @staticmethod
    def w_CALL_METHOD(
        vm: "SPyVM",
        wam_obj: "W_MetaArg",
        wam_method: "W_MetaArg",
        *args_wam: "W_MetaArg",
    ) -> "W_OpSpec":
        raise NotImplementedError("this should never be called")

    @staticmethod
    def w_CONVERT_FROM(
        vm: "SPyVM", wam_expT: "W_MetaArg", wam_gotT: "W_MetaArg", wam_x: "W_MetaArg"
    ) -> "W_OpSpec":
        raise NotImplementedError("this should never be called")

    @staticmethod
    def w_CONVERT_TO(
        vm: "SPyVM", wam_expT: "W_MetaArg", wam_gotT: "W_MetaArg", wam_x: "W_MetaArg"
    ) -> "W_OpSpec":
        raise NotImplementedError("this should never be called")


class W_Type(W_Object):
    """
    The default metaclass for SPy types.

    Types are always created in two steps:
      1. forward declaration
      2. definition

    - `W_Type.declare(fqn)` creates a type in "forward declared" mode.
    - `w_t.define()` turns a declared type into a defined one.
    - `W_Type.from_pyclass()` combines the two above.

    Most builtin types are created by calling @builtin_type, which takes care
    of both declaration and definition.

    However, for some core types this is not possible, because of
    bootstrapping reasons: in particular, in order to evaluate
    @builtin_method we need to import vm.opimpl and vm.function, so any
    type which needs @builtin_method in vm/object.py, vm/opimpl.py and
    vm/function.py needs a lazy definition.

    This can be achieved by declaring the W_Type manually (as done e.g. by
    W_Object and W_Type itself) or by calling
    @builtin_type(lazy_definition=True) (as done e.g. by W_OpSpec). By
    convention, the .define() is called at the beginning of vm.py.
    """

    fqn: FQN
    _pyclass: Optional[Type[W_Object]]
    _dict_w: Optional[dict[str, W_Object]]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        cls = self.__class__.__name__
        raise TypeError(
            f"cannot instantiate {cls} directly. Use {cls}.declare " + f"or {cls}.new"
        )

    def is_defined(self) -> bool:
        return self._dict_w is not None

    @property
    def dict_w(self) -> dict[str, W_Object]:
        if self._dict_w is None:
            m = f"The type {self.fqn} is declared but not defined yet"
            raise Exception(m)
        else:
            return self._dict_w

    @property
    def pyclass(self) -> Type[W_Object]:
        if self._pyclass is None:
            m = f"The type {self.fqn} is declared but not defined yet"
            raise Exception(m)
        else:
            return self._pyclass

    @classmethod
    def declare(cls, fqn: FQN) -> Self:
        """
        Create a new type in the "forward declaration" state
        """
        w_T = super().__new__(cls)
        w_T.fqn = fqn
        w_T._pyclass = None
        w_T._dict_w = None
        return w_T

    @classmethod
    def from_pyclass(cls, fqn: FQN, pyclass: Type[W_Object]) -> Self:
        """
        Declare AND define a new builtin type.
        """
        w_T = cls.declare(fqn)
        w_T.define(pyclass)
        return w_T

    def define(
        self,
        pyclass: Type[W_Object],
        extra_dict_w: Optional[dict[str, W_Object]] = None,
    ) -> None:
        """
        Turn a declared type into a defined type, using the given pyclass and body.
        """
        from spy.vm.member import Member, W_Member

        assert not self.is_defined(), "cannot call W_Type.setup() twice"
        self._pyclass = pyclass
        self._dict_w = {}

        # initialize W_Member
        for field, t in self._pyclass.__annotations__.items():
            if member := Member.from_annotation(t):
                # if we have this declaration:
                #    w_x: Annotated[W_I32, Member('x')]
                #
                # member == Member('x')
                # field == 'w_x'
                # w_T is B.w_i32
                w_T = typing.get_args(t)[0]._w  # W_I32
                w_member = W_Member(member.name, field, w_T)
                self._dict_w[member.name] = w_member

        # lazy evaluation of @builtin methods decorators
        for name, value in self._pyclass.__dict__.items():
            if hasattr(value, "spy_builtin_method"):
                self._init_builtin_method(value)
            elif isinstance(value, builtin_class_attr):
                self._dict_w[value.name] = value.w_val

        # copy the content of extra_dict_w into our _dict_w
        if extra_dict_w:
            for name, w_value in extra_dict_w.items():
                assert name not in self._dict_w, "need to think what to do"
                self._dict_w[name] = w_value

        # add __eq__ and __ne__ if needed
        self._storage_sanity_check(pyclass)
        if pyclass.__spy_storage_category__ == "value":
            # autogen __eq__ and __ne__ if possible
            self._add_eq_ne_maybe(pyclass)

    def _storage_sanity_check(self, pyclass: Type[W_Object]) -> None:
        storage = pyclass.__spy_storage_category__
        if storage == "reference":
            # ref types cannot ovverride interp-level __hash__ or  __eq__
            assert pyclass.__hash__ is object.__hash__
            assert pyclass.__eq__ is object.__eq__
        elif storage == "value":
            if pyclass.spy_key is W_Object.spy_key:
                n = pyclass.__name__
                msg = f"class {n} is a value type but does not override spy_key"
                raise TypeError(msg)
        else:
            msg = f"Invalid value for __spy_storage_category__: {storage}"
            raise TypeError(msg)

    def _add_eq_ne_maybe(self, pyclass: Type[W_Object]) -> None:
        """
        Automatically generate __eq__ and __new__ based on spy_key
        """
        from spy.vm.modules.operator.binop import MM

        assert pyclass.__spy_storage_category__ == "value"
        assert self._dict_w is not None
        T = Annotated[W_Object, self]

        if MM.lookup("==", self, self) is None and "__eq__" not in self._dict_w:
            # no suitable __eq__ found, generate one
            @builtin_method("__eq__")  # type: ignore
            @staticmethod
            def w_eq(vm: "SPyVM", w_self: T, w_other: T) -> "W_Bool":
                k1 = w_self.spy_key(vm)
                k2 = w_other.spy_key(vm)
                return vm.wrap(k1 == k2)

            self._init_builtin_method(w_eq)

        if MM.lookup("!=", self, self) is None and "__ne__" not in self._dict_w:
            # no suitable __ne__ found, generate one
            @builtin_method("__ne__")  # type: ignore
            @staticmethod
            def w_ne(vm: "SPyVM", w_self: T, w_other: T) -> "W_Bool":
                k1 = w_self.spy_key(vm)
                k2 = w_other.spy_key(vm)
                return vm.wrap(k1 != k2)

            self._init_builtin_method(w_ne)

    def define_from_classbody(self, vm: "SPyVM", body: "ClassBody") -> None:
        raise NotImplementedError

    def _init_builtin_method(self, statmeth: staticmethod) -> None:
        """
        Turn @builtin_method into a W_BuiltinFunc and @builtin_property
        into a W_Property
        """
        from spy.vm.builtin import make_builtin_func
        from spy.vm.opspec import W_MetaArg, W_OpSpec
        from spy.vm.primitive import W_Bool, W_Dynamic
        from spy.vm.property import W_ClassMethod, W_Property, W_StaticMethod
        from spy.vm.str import W_Str

        pyfunc = statmeth.__func__
        appname, color, kind, what = statmeth.spy_builtin_method  # type: ignore
        assert what in ("method", "staticmethod", "classmethod", "property")

        # create the W_BuiltinFunc. Make it possible to use the string
        # 'W_MyClass' in annotations
        extra_types = {
            self.pyclass.__name__: Annotated[self.pyclass, self],
            "W_MetaArg": W_MetaArg,
            "W_OpSpec": W_OpSpec,
            "W_Str": W_Str,
            "W_Bool": W_Bool,
            "W_Dynamic": W_Dynamic,
        }
        w_func = make_builtin_func(
            pyfunc,
            namespace=self.fqn,
            funcname=appname,
            qualifiers=[],
            color=color,
            kind=kind,
            extra_types=extra_types,
        )
        if what == "method":
            self.dict_w[appname] = w_func
        elif what == "staticmethod":
            self.dict_w[appname] = W_StaticMethod(w_func)
        elif what == "classmethod":
            self.dict_w[appname] = W_ClassMethod(w_func)
        else:
            self.dict_w[appname] = W_Property(w_func)

    # Union[W_Type, W_NoneType] means "either a W_Type or B.w_None"
    @property
    def w_base(self) -> Union["W_Type", "W_NoneType"]:
        from spy.vm.b import B

        if self is B.w_object or self is B.w_dynamic:
            return B.w_None
        basecls = self.pyclass.__base__
        assert basecls is not None
        assert issubclass(basecls, W_Object)
        assert isinstance(basecls._w, W_Type)
        return basecls._w

    def __repr__(self) -> str:
        hints = [] if self.is_defined() else ["fwdecl"]
        hints += self.repr_hints()
        if hints:
            s_hints = ", ".join(hints)
            s_hints = f" ({s_hints})"
        else:
            s_hints = ""

        addr = ""
        # addr = f' at 0x{id(self):x}'
        return f"<spy type '{self.fqn.human_name}'{s_hints}{addr}>"

    def repr_hints(self) -> list[str]:
        return []

    def is_reference_type(self, vm: "SPyVM") -> bool:
        return self.pyclass.__spy_storage_category__ == "reference"

    def is_struct(self, vm: "SPyVM") -> bool:
        return False

    def get_mro(self) -> Sequence["W_Type"]:
        """
        Return a list of all the supertypes.
        """
        mro = []
        w_T: Union["W_Type", "W_NoneType"] = self
        while w_T is not B.w_None:
            assert isinstance(w_T, W_Type)
            mro.append(w_T)
            w_T = w_T.w_base
        return mro

    def spy_dir(self, vm: "SPyVM") -> set[str]:
        names: set[str] = set()
        for w_T in self.get_mro():
            names.update(w_T.dict_w.keys())
        return names

    def lookup(self, name: str) -> Optional[W_Object]:
        """
        Lookup the given attribute into the applevel dict
        """
        for w_T in self.get_mro():
            if w_obj := w_T.dict_w.get(name):
                return w_obj
        return None

    def lookup_func(self, name: str) -> Optional["W_Func"]:
        """
        Like lookup, but ensure it's a W_Func.
        """
        from spy.vm.function import W_Func

        w_obj = self.lookup(name)
        if w_obj:
            assert isinstance(w_obj, W_Func)
            return w_obj
        return None

    def lookup_blue_func(self, name: str) -> Optional["W_Func"]:
        """
        Like lookup_func, but also check that the function is blue
        """
        from spy.vm.function import W_Func

        w_obj = self.lookup(name)
        if w_obj:
            assert isinstance(w_obj, W_Func)
            assert w_obj.color == "blue"
            return w_obj
        return None

    # ======== app-level interface ========

    # this is the equivalent of CPython's typeobject.c:type_getattro
    @builtin_method("__getattribute__", color="blue", kind="metafunc")
    @staticmethod
    def w_GETATTRIBUTE(
        vm: "SPyVM", wam_T: "W_MetaArg", wam_name: "W_MetaArg"
    ) -> "W_OpSpec":
        from spy.vm.opspec import W_MetaArg, W_OpSpec

        if wam_T.color != "blue":
            # it's unclear how to implement getattr on red types, since we
            # need to have access to their dict.
            raise WIP("getattr on red types")

        w_T = wam_T.w_blueval
        assert isinstance(w_T, W_Type)
        name = wam_name.blue_unwrap_str(vm)

        # 1. try to lookup the attribute on the metatype. If it's a
        # descriptor, call it.
        w_meta_T = vm.dynamic_type(w_T)
        w_meta_attr = w_meta_T.lookup(name)
        if w_meta_attr is not None:
            if w_get := vm.dynamic_type(w_meta_attr).lookup_func("__get__"):
                wam_meta_attr = W_MetaArg.from_w_obj(vm, w_meta_attr)
                return vm.fast_metacall(w_get, [wam_meta_attr, wam_T])

        # 2. Look in the __dict__ of this type and its bases
        w_attr = w_T.lookup(name)
        if w_attr is not None:
            # implement descriptor functionality, if any
            if w_get := vm.dynamic_type(w_attr).lookup_func("__get__"):
                raise WIP("implement me: descriptor accessed via class")

            # normal attribute in the class body, just return it
            return W_OpSpec.const(w_attr)

        # 3. if we found a normal attribute on the metatype, return it
        if w_meta_attr is not None:
            raise WIP("implement me: normal attribute on the metatype")

        # 4. attribute not found
        return W_OpSpec.NULL

    @builtin_method("__call__", color="blue", kind="metafunc")
    @staticmethod
    def w_CALL(vm: "SPyVM", wam_t: "W_MetaArg", *args_wam: "W_MetaArg") -> "W_OpSpec":
        """
        Calling a type means to instantiate it, by calling its __new__
        """
        from spy.vm.function import W_Func
        from spy.vm.opspec import W_OpSpec

        if wam_t.color != "blue":
            err = SPyError(
                "W_TypeError",
                f"instantiation of red types is not yet supported",
            )
            err.add("error", f"this is red", loc=wam_t.loc)
            raise err

        w_T = wam_t.w_blueval
        assert isinstance(w_T, W_Type)

        # try to call __new__
        if w_new := w_T.lookup_func("__new__"):
            # this is a bit of ad-hoc logic around normal __new__ vs metafunc
            # __new__: when it's a metafunc we also want to pass the MetaArg of
            # the type itself (so that the function can reach
            # e.g. wam_p.w_blueval), but for normal __new__ by default we
            # don't pass it (because usually it's not needed)
            if w_new.w_functype.kind == "metafunc":
                new_args_wam = [wam_t] + list(args_wam)
            else:
                new_args_wam = list(args_wam)

            w_opspec = vm.fast_metacall(w_new, new_args_wam)
            return w_opspec

        # no __new__, error out
        clsname = w_T.fqn.human_name
        err = SPyError("W_TypeError", f"cannot instantiate `{clsname}`")
        err.add("error", f"`{clsname}` does not have a method `__new__`", loc=wam_t.loc)
        if wam_t.sym:
            err.add("note", f"{clsname} defined here", wam_t.sym.loc)
        raise err

    @builtin_method("__call_method__", color="blue", kind="metafunc")
    @staticmethod
    def w_CALL_METHOD(
        vm: "SPyVM", wam_T: "W_MetaArg", wam_name: "W_MetaArg", *args_wam: "W_MetaArg"
    ) -> "W_OpSpec":
        """
        Calling a method on a type: we look into the type dict and try to
        call @staticmethod or @classmethod, if present.
        """
        from spy.vm.function import W_Func
        from spy.vm.opspec import W_OpSpec
        from spy.vm.property import W_ClassMethod, W_StaticMethod

        if wam_T.color != "blue":
            raise WIP("__call_method__ on red types")

        w_T = wam_T.w_blueval
        assert isinstance(w_T, W_Type)
        name = wam_name.blue_unwrap_str(vm)
        w_meth = w_T.lookup(name)
        if w_meth is None:
            return W_OpSpec.NULL

        if isinstance(w_meth, W_StaticMethod):
            new_args_wam = list(args_wam)
        elif isinstance(w_meth, W_ClassMethod):
            new_args_wam = [wam_T] + list(args_wam)
        elif isinstance(w_meth, W_Func):
            raise WIP(
                f"this is a method, not a staticmethod or classmethod "
                f"(we should emit a better error)"
            )
        else:
            raise WIP(f"cannot call object {w_meth} (we should emit a better error)")

        w_func = w_meth.w_obj
        if not isinstance(w_func, W_Func):
            raise WIP(
                f"cannot call object {w_meth.w_obj} (we should emit a better error)"
            )

        w_opspec = vm.fast_metacall(w_func, new_args_wam)
        # if we return a simple opspec, it will be called with arguments
        # [wam_name, *args_wam]. But what we want is to call it with just
        # *args_wam. This is the equivalent of passing "list(args_wam)" in
        # op_CALL.
        if w_opspec.is_simple():
            w_opspec._args_wam = new_args_wam
        return w_opspec


# helpers
# =======


@dataclass
class ClassBody:
    """
    Collect fields, methods and other class attributes which are evaluated
    inside a 'class' statement, and passed to W_Type.define_from_classbody to
    define user-defined types.
    """

    fields_w: dict[str, "W_Field"]
    dict_w: dict[str, W_Object]


# Initial setup of the 'builtins' module
# ======================================

W_Object._w = W_Type.declare(FQN("builtins::object"))
W_Type._w = W_Type.declare(FQN("builtins::type"))
B.add("object", W_Object._w)
B.add("type", W_Type._w)
