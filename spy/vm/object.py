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
from typing import (TYPE_CHECKING, ClassVar, Type, Any, Optional, Union,
                    Callable, Annotated, Self)
from dataclasses import dataclass
from spy.ast import Color
from spy.fqn import FQN
from spy.errors import SPyTypeError
from spy.vm.b import B

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM
    from spy.vm.primitive import W_Void, W_Dynamic
    from spy.vm.function import W_Func
    from spy.vm.opimpl import W_OpImpl, W_OpArg

def builtin_method(name: str, *, color: Color = 'red') -> Any:
    """
    Turn an interp-level method into an app-level one.

    This decorator just put a mark on the method. The actual job is done by
    W_Type._init_builtin_method().
    """
    def decorator(fn: Callable) -> Callable:
        assert isinstance(fn, staticmethod), 'missing @staticmethod'
        fn.spy_builtin_method = (name, color)  # type: ignore
        return fn
    return decorator

# Basic setup of the object model: <object> and <type>
# =====================================================

# NOTE: contrarily to all the other builtin types, for W_Object and W_Type we
# cannot use @B.builtin_type, because of bootstrapping issues.  See also the
# section "Initial setup of the 'builtins' module"

class W_Object:
    """
    The root of SPy object hierarchy
    """

    _w: ClassVar['W_Type']                         # set by @builtin_type

    # Storage category:
    #   - 'value': compares by value, don't have an identity, 'is' is
    #     forbidden. E.g., i32, f64, str.
    #   - 'reference': compare by identity
    __spy_storage_category__ = 'value'

    def __repr__(self) -> str:
        fqn = self._w.fqn
        addr = f'0x{id(self):x}'
        return f'<spy instance: type={fqn.human_name}, id={addr}>'

    def spy_get_w_type(self, vm: 'SPyVM') -> 'W_Type':
        pyclass = type(self)
        assert pyclass.__dict__['_w'] is not None, 'missing @builtin_type?'
        return pyclass._w

    def spy_unwrap(self, vm: 'SPyVM') -> Any:
        spy_type = vm.dynamic_type(self).fqn
        py_type = self.__class__.__name__
        raise Exception(f"Cannot unwrap app-level objects of type {spy_type} "
                        f"(interp-level type: {py_type})")


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
    # the various w_GETATTR & co.  These must be *static methods* on the
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
    #        def w_meta_CALL(...): ...
    #
    # Here spytype will automatically create the metaclass W_Meta_Foo, and it
    # will assign W_Meta_Foo.w_CALL = W_Foo.w_meta_CALL

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
    def w_EQ(vm: 'SPyVM', wop_a: 'W_OpArg', wop_b: 'W_OpArg') -> 'W_OpImpl':
        raise NotImplementedError('this should never be called')

    @staticmethod
    def w_NE(vm: 'SPyVM', wop_a: 'W_OpArg', wop_b: 'W_OpArg') -> 'W_OpImpl':
        raise NotImplementedError('this should never be called')

    @staticmethod
    def w_GETATTR(vm: 'SPyVM', wop_obj: 'W_OpArg',
                  wop_attr: 'W_OpArg') -> 'W_OpImpl':
        raise NotImplementedError('this should never be called')

    @staticmethod
    def w_SETATTR(vm: 'SPyVM', wop_obj: 'W_OpArg', wop_attr: 'W_OpArg',
                  wop_v: 'W_OpArg') -> 'W_OpImpl':
        raise NotImplementedError('this should never be called')

    @staticmethod
    def w_GETITEM(vm: 'SPyVM', wop_obj: 'W_OpArg',
                  wop_i: 'W_OpArg') -> 'W_OpImpl':
        raise NotImplementedError('this should never be called')

    @staticmethod
    def w_SETITEM(vm: 'SPyVM', wop_obj: 'W_OpArg', wop_i: 'W_OpArg',
                  wop_v: 'W_OpArg') -> 'W_OpImpl':
        raise NotImplementedError('this should never be called')

    @staticmethod
    def w_CALL(vm: 'SPyVM', wop_obj: 'W_OpArg',
                *args_wop: 'W_OpArg') -> 'W_OpImpl':
        raise NotImplementedError('this should never be called')

    @staticmethod
    def w_CALL_METHOD(vm: 'SPyVM', wop_obj: 'W_OpArg', wop_method: 'W_OpArg',
                      *args_wop: 'W_OpArg') -> 'W_OpImpl':
        raise NotImplementedError('this should never be called')

    @staticmethod
    def w_CONVERT_FROM(vm: 'SPyVM', w_T: 'W_Type',
                       wop_x: 'W_OpArg') -> 'W_OpImpl':
        raise NotImplementedError('this should never be called')

    @staticmethod
    def w_CONVERT_TO(vm: 'SPyVM', w_T: 'W_Type',
                     wop_x: 'W_OpArg') -> 'W_OpImpl':
        raise NotImplementedError('this should never be called')



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
    @builtin_type(lazy_definition=True) (as done e.g. by W_OpImpl). By
    convention, the .define() is called at the beginning of vm.py.
    """
    __spy_storage_category__ = 'reference'
    fqn: FQN
    _pyclass: Optional[Type[W_Object]]
    spy_members: dict[str, 'Member']
    _dict_w: Optional[dict[str, W_Object]]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        cls = self.__class__.__name__
        raise TypeError(
            f'cannot instantiate {cls} directly. Use {cls}.declare ' +
            f'or {cls}.new'
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
        w_type = super().__new__(cls)
        w_type.fqn = fqn
        w_type._pyclass = None
        w_type._dict_w = None
        return w_type

    @classmethod
    def from_pyclass(cls, fqn: FQN, pyclass: Type[W_Object]) -> Self:
        """
        Declare AND define a new builtin type.
        """
        w_type = cls.declare(fqn)
        w_type.define(pyclass)
        return w_type

    def define(self, pyclass: Type[W_Object]) -> None:
        """
        Turn a declared type into a defined type, using the given pyclass.
        """
        assert not self.is_defined(), 'cannot call W_Type.setup() twice'
        self._pyclass = pyclass
        self._dict_w = {}

        # setup spy_members
        self.spy_members = {}
        for field, t in self._pyclass.__annotations__.items():
            member = Member.from_annotation_maybe(t)
            if member is not None:
                member.field = field
                member.w_type = typing.get_args(t)[0]._w
                self.spy_members[member.name] = member

        # lazy evaluation of @builtin methods decorators
        for name, value in self._pyclass.__dict__.items():
            if hasattr(value, 'spy_builtin_method'):
                self._init_builtin_method(value)

    def define_from_classbody(self, body: 'ClassBody') -> None:
        raise NotImplementedError

    def _init_builtin_method(self, statmeth: staticmethod) -> None:
        "Turn the @builtin_method into a W_BuiltinFunc"
        from spy.vm.builtin import builtin_func
        from spy.vm.opimpl import W_OpArg, W_OpImpl
        appname, color = statmeth.spy_builtin_method  # type: ignore
        pyfunc = statmeth.__func__

        # sanity check: __MAGIC__ methods should be blue
        if appname in (
                '__ADD__', '__SUB__', '__MUL__', '__DIV__',
                '__EQ__', '__NE__', '__LT__', '__LE__', '__GT__', '__GE__',
                '__GETATTR__', '__SETATTR__',
                '__GETITEM__', '__SETITEM__',
                '__CALL__', '__CALL_METHOD__',
                '__CONVERT_FROM__', '__CONVERT_TO__',
        ) and color != 'blue':
            # XXX we should raise a more detailed exception
            fqn = self.fqn.human_name
            msg = f"method `{fqn}.{appname}` should be blue, but it's {color}"
            raise SPyTypeError(msg)

        # create the @builtin_func decorator, and make it possible to use the
        # string 'W_MyClass' in annotations
        extra_types = {
            self.pyclass.__name__: Annotated[self.pyclass, self],
            'W_OpArg': W_OpArg,
            'W_OpImpl': W_OpImpl,
        }
        decorator = builtin_func(
            namespace = self.fqn,
            funcname = appname,
            qualifiers = [],
            color = color,
            extra_types = extra_types,
        )
        # apply the decorator and store the method in the applevel dict
        w_meth = decorator(pyfunc)
        self.dict_w[appname] = w_meth

    # Union[W_Type, W_Void] means "either a W_Type or B.w_None"
    @property
    def w_base(self) -> Union['W_Type', 'W_Void']:
        from spy.vm.b import B
        if self is B.w_object or self is B.w_dynamic:
            return B.w_None
        basecls = self.pyclass.__base__
        assert issubclass(basecls, W_Object)
        assert isinstance(basecls._w, W_Type)
        return basecls._w

    def __repr__(self) -> str:
        hints = [] if self.is_defined() else ['fwdecl']
        hints += self.repr_hints()
        if hints:
            s_hints = ', '.join(hints)
            s_hints = f' ({s_hints})'
        else:
            s_hints = ''
        return f"<spy type '{self.fqn.human_name}'{s_hints}>"

    def repr_hints(self) -> list[str]:
        return []

    def is_reference_type(self, vm: 'SPyVM') -> bool:
        return self.pyclass.__spy_storage_category__ == 'reference'

    def is_struct(self, vm: 'SPyVM') -> bool:
        return False

    def lookup_func(self, name: str) -> Optional['W_Func']:
        """
        Lookup the given attribute into the applevel dict, and ensure it's
        a W_Func.
        """
        from spy.vm.function import W_Func
        # look in our dict
        if w_obj := self.dict_w.get(name):
            assert isinstance(w_obj, W_Func)
            return w_obj

        # look in the superclass
        w_base = self.w_base
        if isinstance(w_base, W_Type):
            return w_base.lookup_func(name)

        # not found
        return None

    def lookup_blue_func(self, name: str) -> Optional['W_Func']:
        """
        Like lookup_func, but also check that the function is blue
        """
        w_obj = self.lookup_func(name)
        if w_obj:
            assert w_obj.color == 'blue'
        return w_obj

    # ======== app-level interface ========

    @builtin_method('__CALL__', color='blue')
    @staticmethod
    def w_CALL(vm: 'SPyVM', wop_t: 'W_OpArg',
               *args_wop: 'W_OpArg') -> 'W_OpImpl':
        """
        Calling a type means to instantiate it.

        First try to use __NEW__ if defined, otherwise fall back to __new__.
        """
        from spy.vm.function import W_Func
        from spy.vm.opimpl import W_OpImpl

        if wop_t.color != 'blue':
            err = SPyTypeError(
                f"instantiation of red types is not yet supported")
            err.add('error', f"this is red", loc=wop_t.loc)
            raise err

        w_type = wop_t.w_blueval
        assert isinstance(w_type, W_Type)

        # Call __NEW__, if present
        w_NEW = w_type.dict_w.get('__NEW__')
        if w_NEW is not None:
            assert isinstance(w_NEW, W_Func), 'XXX raise proper exception'
            w_res = vm.fast_call(w_NEW, [wop_t] + list(args_wop))
            assert isinstance(w_res, W_OpImpl)
            return w_res

        # else, fall back to __new__
        w_new = w_type.dict_w.get('__new__')
        if w_new is not None:
            assert isinstance(w_new, W_Func), 'XXX raise proper exception'
            return W_OpImpl(w_new)

        # no __NEW__ nor __new__, error out
        clsname = w_type.fqn.human_name
        err = SPyTypeError(f"cannot instantiate `{clsname}`")
        err.add('error', f"`{clsname}` does not have a method `__new__`",
                loc=wop_t.loc)
        if wop_t.sym:
            err.add('note', f"{clsname} defined here", wop_t.sym.loc)
        raise err



# helpers
# =======

FIELDS_T = dict[str, W_Type]
METHODS_T = dict[str, 'W_Func']

@dataclass
class ClassBody:
    """
    Collect fields and methods which are evaluated inside a 'class'
    statement, and passed to W_Type.define_from_classbody to define
    user-defined types.
    """
    fields: FIELDS_T
    methods: METHODS_T


class Member:
    """
    Represent a property of a W_ class. Use it like this:

    @builtin_type('MyClass')
    class W_MyClass(W_Object):
        w_x: Annotated[W_I32, Member('x')]

    This will add an app-level attribute "x" to the class, corresponding to
    the interp-level attribute "w_x".
    """
    name: str
    field: str        # set later by W_Type.__init__
    w_type: 'W_Type'  # set later by W_Type.__init__

    def __init__(self, name: str) -> None:
        self.name = name

    @staticmethod
    def from_annotation_maybe(t: Any) -> Optional['Member']:
        """
        Return the Member instance found in the annotation metadata, if any.
        """
        for meta in getattr(t, '__metadata__', []):
            if isinstance(meta, Member):
                return meta
        return None

def make_metaclass_maybe(fqn: FQN, pyclass: Type[W_Object],
                         lazy_definition: bool) -> Type[W_Type]:
    """
    Synthesize an app-level metaclass for the corresponding interp-level
    pyclass, if needed.

    Normally, for each interp-level class W_Foo, we create an app-level type
    which is an instance of W_Type.

    However, W_Foo can request the creation of a custom metaclass by
    implementing any of the supported w_meta_* methods.

    Example:

    @builtin_type('ext', 'Foo')
    class W_Foo(W_Object):
        pass
    ==> creates:
    w_footype = W_Type('ext::Foo', pyclass=W_Foo)


    @builtin_type('ext', 'Bar')
    class W_Bar(W_Object):
        @staticmethod
        def w_meta_GETITEM(...):
            ..
    ==> creates:
    class W_BarType(W_Type):
        @builtin_method('__GETITEM__', color='blue')
        @staticmethod
        def w_GETITEM(...):
            ...
    w_bartype = W_BarType('ext::Bar', pyclass=W_Bar)

    The relationship between W_Bar and W_BarType is the following:

    w_Bar = vm.wrap(W_Bar)
    w_bar_type = vm.wrap(W_BarType)
    assert vm.dynamic_type(w_Bar) is w_bar_type
    """
    from spy.vm.builtin import builtin_method
    if (not hasattr(pyclass, 'w_meta_CALL') and
        not hasattr(pyclass, 'w_meta_GETITEM') and
        not hasattr(pyclass, 'w_meta_GETATTR')):
        # no metaclass needed
        return W_Type

    metaname = f'{fqn.symbol_name}Type'
    metafqn = fqn.namespace.join(metaname)

    class W_MetaType(W_Type):
        __name__ = f'W_{metaname}'
        __qualname__ = __name__

    if hasattr(pyclass, 'w_meta_CALL'):
        fn = pyclass.w_meta_CALL
        decorator = builtin_method('__CALL__', color='blue')
        W_MetaType.w_CALL = decorator(staticmethod(fn))  # type: ignore
    if hasattr(pyclass, 'w_meta_GETITEM'):
        fn = pyclass.w_meta_GETITEM
        decorator = builtin_method('__GETITEM__', color='blue')
        W_MetaType.w_GETITEM = decorator(staticmethod(fn))  # type: ignore
    if hasattr(pyclass, 'w_meta_GETATTR'):
        fn = pyclass.w_meta_GETATTR
        decorator = builtin_method('__GETATTR__', color='blue')
        W_MetaType.w_GETATTR = decorator(staticmethod(fn))  # type: ignore

    if lazy_definition:
        W_MetaType._w = W_Type.declare(metafqn)
    else:
        W_MetaType._w = W_Type.from_pyclass(metafqn, W_MetaType)
    return W_MetaType


# Initial setup of the 'builtins' module
# ======================================

W_Object._w = W_Type.declare(FQN('builtins::object'))
W_Type._w = W_Type.declare(FQN('builtins::type'))
B.add('object', W_Object._w)
B.add('type', W_Type._w)
