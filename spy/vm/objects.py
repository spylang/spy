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

SPy app-level types are instances of W_TypeObject, which is basically a thin
wrapper around the correspindig interp-level W_* class.
"""

class W_Object:
    """
    The root of SPy object hierarchy
    """

    _w = None # set later

    def __repr__(self):
        typename = self._w.name
        addr = f'0x{id(self):x}'
        return f'<spy instance: type={typename}, id={addr}>'


class W_TypeObject(W_Object):
    """
    The default metaclass for SPy types.

    This is basically a thin wrapper around W_* classes.
    """

    _w = None # set later

    def __init__(self, name, pyclass):
        assert issubclass(pyclass, W_Object)
        self.name = name
        self.pyclass = pyclass

    @property
    def w_base(self):
        return self.__class__.__base__._w

    def __repr__(self):
        return f"<spy type '{self.name}'>"

W_Object._w = W_TypeObject('object', W_Object)
W_TypeObject._w = W_TypeObject('type', W_TypeObject)
