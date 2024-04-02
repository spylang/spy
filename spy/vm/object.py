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
from typing import TYPE_CHECKING, ClassVar, Type, Any
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM
    from spy.vm.str import W_Str

# Basic setup of the object model: <object> and <type>
# =====================================================

class W_Object:
    """
    The root of SPy object hierarchy
    """

    _w: ClassVar['W_Type']  # set later

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
    # Subclasses of W_Object have two different options to implement their own
    # semantics for the operators:
    #
    #   1. The can implement the operator itself, by overriding op_GETATTR:
    #      this must be a *static method* on the class, and must return an
    #      opimpl.
    #
    #   2. For convenience, subclasses can also decide to implement
    #      opimpl_getattr: in this case, the default logic for op_GETATTR is
    #      to simply return that opimpl.
    #
    # The actual logic for the SPy VM resides in the 'operator' module (see
    # spy/vm/modules/operator).

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
                   w_attr: 'W_Str') -> 'W_Object':
        raise NotImplementedError('this should never be called')

    def opimpl_getattr(self, vm: 'SPyVM', w_attr: 'W_Str') -> 'W_Object':
        raise NotImplementedError('this should never be called')

    @staticmethod
    def op_SETATTR(vm: 'SPyVM', w_type: 'W_Type', w_attr: 'W_Str',
                   w_vtype: 'W_Type') -> 'W_Object':
        raise NotImplementedError('this should never be called')

    def opimpl_setattr(self, vm: 'SPyVM', w_attr: 'W_Str',
                       w_val: 'W_Object') -> None:
        raise NotImplementedError('this should never be called')


class W_Type(W_Object):
    """
    The default metaclass for SPy types.

    This is basically a thin wrapper around W_* classes.
    """

    name: str
    pyclass: Type[W_Object]

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

W_Object._w = W_Type('object', W_Object)
W_Type._w = W_Type('type', W_Type)


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

w_DynamicType = W_Type('dynamic', W_Object)


# Other types
# ============

def spytype(name: str, metaclass: Type[W_Type] = W_Type) -> Any:
    """
    Class decorator to simplify the creation of SPy types.

    Given a W_* class, it automatically creates the corresponding instance of
    W_Type and attaches it to the W_* class.
    """
    def decorator(pyclass: Type[W_Object]) -> Type[W_Object]:
        pyclass._w = metaclass(name, pyclass)
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
