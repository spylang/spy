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
instance `W_i32(100)`, which is a wrapper around the interp-level object `100`.

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
        if self is W_Object._w:
            return W_void._w_singleton
        basecls = self.pyclass.__base__
        assert issubclass(basecls, W_Object)
        return basecls._w

    def __repr__(self) -> str:
        return f"<spy type '{self.name}'>"

    def spy_unwrap(self, vm: 'SPyVM') -> Any:
        return self.pyclass

W_Object._w = W_Type('object', W_Object)
W_Type._w = W_Type('type', W_Type)


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


# Other types
# ============

@spytype('void')
class W_void(W_Object):
    """
    Equivalent of Python's NoneType.

    This is a singleton: there should be only one instance of this class,
    which is w_None.
    """

    _w_singleton: ClassVar['W_void']

    def __init__(self) -> None:
        # this is just a sanity check: we don't want people to be able to
        # create additional instances of W_void
        raise Exception("You cannot instantiate W_void")

    def __repr__(self) -> str:
        return '<spy None>'

    def spy_unwrap(self, vm: 'SPyVM') -> Any:
        return None

W_void._w_singleton = W_void.__new__(W_void)


@spytype('i32')
class W_i32(W_Object):
    value: fixedint.Int32

    def __init__(self, value: int | fixedint.Int32) -> None:
        assert type(value) in (int, fixedint.Int32)
        self.value = fixedint.Int32(value)

    def __repr__(self) -> str:
        return f'W_i32({self.value})'

    def spy_unwrap(self, vm: 'SPyVM') -> Any:
        return self.value


@spytype('bool')
class W_bool(W_Object):
    value: bool
    #
    _w_singleton_True: ClassVar['W_bool']
    _w_singleton_False: ClassVar['W_bool']

    def __init__(self, value: bool) -> None:
        # this is just a sanity check: we don't want people to be able to
        # create additional instances of W_bool
        raise Exception("You cannot instantiate W_bool. Use vm.wrap().")

    @staticmethod
    def _make_singleton(value: bool) -> 'W_bool':
        w_obj = W_bool.__new__(W_bool)
        w_obj.value = value
        return w_obj

    def __repr__(self) -> str:
        return f'W_bool({self.value})'

    def spy_unwrap(self, vm: 'SPyVM') -> Any:
        return self.value

W_bool._w_singleton_True = W_bool._make_singleton(True)
W_bool._w_singleton_False = W_bool._make_singleton(False)

@spytype('str')
class W_str(W_Object):
    """
    An unicode string.

    Internally, it is represented as UTF-8.
    """
    utf8_bytes: bytes

    def __init__(self, s: str) -> None:
        self.utf8_bytes = s.encode('utf-8')

    def _as_str(self) -> str:
        return self.utf8_bytes.decode('utf-8')

    def __repr__(self) -> str:
        s = self._as_str()
        return f'W_str({s!r})'

    def spy_unwrap(self, vm: 'SPyVM') -> Any:
        return self._as_str()
