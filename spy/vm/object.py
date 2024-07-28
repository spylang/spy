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

import fixedint
import typing
from typing import TYPE_CHECKING, ClassVar, Type, Any, Annotated, Optional
from spy.fqn import QN
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM
    from spy.vm.str import W_Str

# Basic setup of the object model: <object> and <type>
# =====================================================

class W_Object:
    """
    The root of SPy object hierarchy
    """

    _w: ClassVar['W_Type']                         # set later by @spytype
    __spy_members__: ClassVar['dict[str, Member]'] # set later by @spytype

    # Storage category:
    #   - 'value': compares by value, don't have an identity, 'is' is
    #     forbidden. E.g., i32, f64, str.
    #   - 'reference': compare by identity
    __spy_storage_category__ = 'value'

    def __repr__(self) -> str:
        typename = self._w.name
        addr = f'0x{id(self):x}'
        return f'<spy instance: type={typename}, id={addr}>'

    def spy_get_w_type(self, vm: 'SPyVM') -> 'W_Type':
        pyclass = type(self)
        assert pyclass._w is not None
        return pyclass._w

    def spy_unwrap(self, vm: 'SPyVM') -> Any:
        spy_type = vm.dynamic_type(self).name
        py_type = self.__class__.__name__
        raise Exception(f"Cannot unwrap app-level objects of type {spy_type} "
                        f"(inter-level type: {py_type})")


    # ==== OPERATOR SUPPORT ====
    #
    # operators are the central concept which drives the semantic of SPy
    # objects. Operators are @blue functions which receive the *types* of the
    # operands, and return an "opimpl", which is a red function which
    # performn the actual operation on the *values*.
    #
    # For example, consider the following expression:
    #     return obj.a
    #
    # In normal Python,  this roughly maps to the following:
    #     return type(obj).__getattribute__(obj, 'a')
    #
    # In SPy, it maps to the following:
    #     opimpl = operator.GETATTR(static_type(obj), 'a')
    #     return opimpl(obj, 'a')
    #
    # Subclasses of W_Object can implement their own operator by overriding
    # the various op_GETATTR & co.  These must be *static methods* on the
    # class, and must return an opimpl.
    #
    #
    # The actual logic for the SPy VM resides in the 'operator' module (see
    # spy/vm/modules/operator).
    #
    # For convenience, pyclasses can also implement meta_op_*: these will be
    # automatically used as operators for their applevel metaclass:
    # strictly-speaking this is not necessary, because one could just write a
    # metaclass manually with all the needed operators, but this makes it much
    # easier. For example:
    #
    #    @spytype('Foo')
    #    class W_Foo(W_Object):
    #        @staticmethod
    #        def meta_op_CALL(...): ...
    #
    # Here spytype will automatically create the metaclass W_Meta_Foo, and it
    # will assign W_Meta_Foo.op_CALL = W_Foo.meta_op_CALL

    @classmethod
    def has_meth_overriden(cls, name: str) -> bool:
        default_meth = getattr(W_Object, name, None)
        meth = getattr(cls, name, None)
        if default_meth is None or meth is None:
            raise ValueError(f'Invalid method name: {name}')
        if default_meth is meth:
            return False
        return True

    @staticmethod
    def op_GETATTR(vm: 'SPyVM', w_type: 'W_Type',
                   w_attr: 'W_Str') -> 'W_Dynamic':
        raise NotImplementedError('this should never be called')

    @staticmethod
    def op_SETATTR(vm: 'SPyVM', w_type: 'W_Type', w_attr: 'W_Str',
                   w_vtype: 'W_Type') -> 'W_Dynamic':
        raise NotImplementedError('this should never be called')

    @staticmethod
    def op_GETITEM(vm: 'SPyVM', w_type: 'W_Type',
                   w_vtype: 'W_Type') -> 'W_Dynamic':
        raise NotImplementedError('this should never be called')

    @staticmethod
    def op_SETITEM(vm: 'SPyVM', w_type: 'W_Type', w_itype: 'W_Type',
                   w_vtype: 'W_Type') -> 'W_Dynamic':
        raise NotImplementedError('this should never be called')

    @staticmethod
    def op_CALL(vm: 'SPyVM', w_type: 'W_Type',
                w_argtypes: 'W_Dynamic') -> 'W_Dynamic':
        raise NotImplementedError('this should never be called')

    @staticmethod
    def op_CALL_METHOD(vm: 'SPyVM', w_type: 'W_Type', w_method: 'W_Str',
                       w_argtypes: 'W_Dynamic') -> 'W_Dynamic':
        raise NotImplementedError('this should never be called')


class W_Type(W_Object):
    """
    The default metaclass for SPy types.

    This is basically a thin wrapper around W_* classes.
    """

    name: str
    pyclass: Type[W_Object]
    __spy_storage_category__ = 'reference'

    def __init__(self, name: str, pyclass: Type[W_Object]):
        assert issubclass(pyclass, W_Object)
        self.name = name
        self.pyclass = pyclass

    @property
    def w_base(self) -> W_Object:
        if self is W_Object._w or self is w_DynamicType:
            return W_Void._w_singleton
        basecls = self.pyclass.__base__
        assert issubclass(basecls, W_Object)
        return basecls._w

    def __repr__(self) -> str:
        return f"<spy type '{self.name}'>"

    def spy_unwrap(self, vm: 'SPyVM') -> Type[W_Object]:
        return self.pyclass

    def is_reference_type(self, vm: 'SPyVM') -> bool:
        return self.pyclass.__spy_storage_category__ == 'reference'

W_Object._w = W_Type('object', W_Object)
W_Object.__spy_members__ = {}
W_Type._w = W_Type('type', W_Type)
W_Type.__spy_members__ = {}

# The <dynamic> type
# ===================
#
# <dynamic> is special:
#
# - it's not a real type, in the sense that you cannot have an instance whose
#   type is `dynamic`
#
# - every class is considered to be a subclass of <dynamic>
#
# - conversion from T to <dynamic> always succeeds (like from T to <object>)
#
# - conversion from <dynamic> to T is always possible but it might fail at
#   runtime (like from <object> to T)
#
# From some point of view, <dynamic> is the twin of <object>, because it acts
# as if it were at the root of the type hierarchy. The biggest difference is
# how operators are dispatched: operations on <object> almost never succeeds,
# while operations on <dynamic> are dispatched to the actual dynamic
# types. For example:
#
#    x: object = 1
#    y: dynamic = 2
#    z: dynamic = 'hello'
#
#    x + 1 # compile-time error: cannot do `<object> + <i32>`
#    y + 1 # succeeds, but the dispatch is done at runtime
#    z + 1 # runtime error: cannot do `<i32> + <str>`
#
# Since it's a compile-time only concept, it doesn't have a corresponding
# W_Dynamic interp-level class. However, we still provide W_Dynamic as an
# annotated version of W_Object: from the mypy static typing point of view,
# it's equivalent to W_Object, but it is recognized by @spy_builtin to
# generate the "correct" w_functype signature.

w_DynamicType = W_Type('dynamic', W_Object) # this is B.w_dynamic
W_Dynamic = Annotated[W_Object, 'W_Dynamic']


# Other types
# ============

class Member:
    """
    Represent a property of a W_ class. Use it like this:

    @spytype('MyClass')
    class W_MyClass(W_Object):
        w_x: Annotated[W_I32, Member('x')]

    This will add an app-level attribute "x" to the class, corresponding to
    the interp-level attribute "w_x".
    """
    name: str
    field: str      # set later by @spytype
    w_type: W_Type  # set later by @spytype

    def __init__(self, name: str) -> None:
        self.name = name


def _get_member_maybe(t: Any) -> Optional[Member]:
    """
    Return the Member instance found in the annotation metadata, if any.
    """
    for meta in getattr(t, '__metadata__', []):
        if isinstance(meta, Member):
            return meta
    return None


def make_metaclass(name: str, pyclass: Type[W_Object]) -> Type[W_Type]:
    """
    Synthesize an app-level metaclass for the corresponding interp-level
    pyclass.

    Example:

    @spytype('Foo')
    class W_Foo(W_Object):
        pass

    this automatically creates:

    class W_Meta_Foo(W_Type):
        ...

    The relationship between Foo and Meta_Foo is the following:

    w_Foo = vm.wrap(W_Foo)
    w_Meta_Foo = vm.wrap(W_Meta_Foo)
    assert vm.dynamic_type(w_Foo) is w_Meta_Foo

    W_Foo can customize the behavior of the metaclass in various ways:

    1. by using `op_meta_*` operators: these automatically becomes operators
       of the metaclass. In particular, `op_meta_CALL` is used to create
       app-level instances of w_Foo.

    2. by using `spy_new`, which automatically synthesize an appropriare
       op_meta_CALL. This is just for convenience.
    """
    metaname = f'Meta_{name}'

    class W_MetaType(W_Type):
        __name__ = f'W_{metaname}'
        __qualname__ = __name__

    if hasattr(pyclass, 'meta_op_CALL'):
        W_MetaType.op_CALL = pyclass.meta_op_CALL  # type: ignore
    elif hasattr(pyclass, 'spy_new'):
        W_MetaType.op_CALL = synthesize_meta_op_CALL(pyclass)  # type: ignore

    W_MetaType._w = W_Type(metaname, W_MetaType)
    return W_MetaType

def fix_annotations(fn: Any, types: dict[str, type]) -> None:
    """
    Substitute lazy annotations expressed as strings with their "real"
    corresponding type.
    """
    for key, T in fn.__annotations__.items():
        if isinstance(T, str) and T in types:
            newT = types[T]
            fn.__annotations__[key] = newT

def synthesize_meta_op_CALL(pyclass: Type[W_Object]) -> Any:
    """
    Given a pyclass which implements spy_new, create an op_CALL for the
    corresponding metaclass. Example:

    class W_Foo(W_Object):
        @staticmethod
        def spy_new(vm: 'SPyVM', w_cls: W_Type, ...) -> 'W_Foo':
            ...

    This function creates an op_CALL method which will be put on W_Meta_Foo.
    W_Meta_Foo.op_CALL returns W_Foo.spy_new as the opimpl.

    Ideally, we would like to be able to write this:

    class W_Foo(W_Object):
        @staticmethod
        @spy_builtin(QN("xxx::new"))
        def spy_new(vm: 'SPyVM', w_cls: W_Type, ...) -> 'W_Foo':
            ...

    But we cannot because spy_builtin is unable to understand the annotation
    'W_Foo' expressed as a string. A lot of the logic here is basically a
    workaround for this.

    Inside, we call fix_annotations to replace 'W_Foo' with the actual
    W_Foo. Once we have done that, we can manually apply @spy_builtin and
    finally vm.wrap() it.
    """
    from spy.vm.sig import spy_builtin
    assert hasattr(pyclass, 'spy_new')
    spy_new = pyclass.spy_new

    def meta_op_CALL(vm: 'SPyVM', w_type: W_Type,
                     w_argtypes: W_Dynamic) -> W_Dynamic:
        fix_annotations(spy_new, {pyclass.__name__: pyclass})
        qn = QN(modname='ext', attr='new') # XXX what modname should we use?
        # manually apply the @spy_builtin decorator to the spy_new function
        spy_builtin(qn)(spy_new)
        return vm.wrap(spy_new)

    return meta_op_CALL

def spytype(name: str) -> Any:
    """
    Class decorator to simplify the creation of SPy types.

    Given a W_* class, it automatically creates the corresponding instance of
    W_Type and attaches it to the W_* class.
    """
    def decorator(pyclass: Type[W_Object]) -> Type[W_Object]:
        W_MetaClass = make_metaclass(name, pyclass)

        pyclass._w = W_MetaClass(name, pyclass)
        # setup __spy_members__
        pyclass.__spy_members__ = {}
        for field, t in pyclass.__annotations__.items():
            member = _get_member_maybe(t)
            if member is not None:
                member.field = field
                member.w_type = typing.get_args(t)[0]._w
                pyclass.__spy_members__[member.name] = member

        return pyclass
    return decorator

@spytype('void')
class W_Void(W_Object):
    """
    Equivalent of Python's NoneType.

    This is a singleton: there should be only one instance of this class,
    which is w_None.
    """

    _w_singleton: ClassVar['W_Void']

    def __init__(self) -> None:
        # this is just a sanity check: we don't want people to be able to
        # create additional instances of W_Void
        raise Exception("You cannot instantiate W_Void")

    def __repr__(self) -> str:
        return '<spy None>'

    def spy_unwrap(self, vm: 'SPyVM') -> None:
        return None

W_Void._w_singleton = W_Void.__new__(W_Void)


@spytype('i32')
class W_I32(W_Object):
    value: fixedint.Int32

    def __init__(self, value: int | fixedint.Int32) -> None:
        assert type(value) in (int, fixedint.Int32)
        self.value = fixedint.Int32(value)

    def __repr__(self) -> str:
        return f'W_I32({self.value})'

    def spy_unwrap(self, vm: 'SPyVM') -> fixedint.Int32:
        return self.value


@spytype('f64')
class W_F64(W_Object):
    value: float

    def __init__(self, value: float) -> None:
        assert type(value) is float
        self.value = value

    def __repr__(self) -> str:
        return f'W_F64({self.value})'

    def spy_unwrap(self, vm: 'SPyVM') -> float:
        return self.value


@spytype('bool')
class W_Bool(W_Object):
    value: bool
    #
    _w_singleton_True: ClassVar['W_Bool']
    _w_singleton_False: ClassVar['W_Bool']

    def __init__(self, value: bool) -> None:
        # this is just a sanity check: we don't want people to be able to
        # create additional instances of W_Bool
        raise Exception("You cannot instantiate W_Bool. Use vm.wrap().")

    @staticmethod
    def _make_singleton(value: bool) -> 'W_Bool':
        w_obj = W_Bool.__new__(W_Bool)
        w_obj.value = value
        return w_obj

    def __repr__(self) -> str:
        return f'W_Bool({self.value})'

    def spy_unwrap(self, vm: 'SPyVM') -> bool:
        return self.value

W_Bool._w_singleton_True = W_Bool._make_singleton(True)
W_Bool._w_singleton_False = W_Bool._make_singleton(False)


@spytype('NotImplementedType')
class W_NotImplementedType(W_Object):
    _w_singleton: ClassVar['W_NotImplementedType']

    def __init__(self) -> None:
        # this is just a sanity check: we don't want people to be able to
        # create additional instances
        raise Exception("You cannot instantiate W_NotImplementedType")


W_NotImplementedType._w_singleton = (
    W_NotImplementedType.__new__(W_NotImplementedType)
)
