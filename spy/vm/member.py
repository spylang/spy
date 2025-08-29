from typing import Annotated, TYPE_CHECKING, Any, Optional
from spy.vm.b import BUILTINS
from spy.vm.object import W_Object, W_Type
from spy.vm.builtin import builtin_method

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM
    from spy.vm.opspec import W_OpArg, W_OpSpec


class Member:
    """
    Annotation to turn an interp-level field into an app-level
    property. Use it like this:

    @builtin_type('MyClass')
    class W_MyClass(W_Object):
        w_x: Annotated[W_I32, Member('x')]

    This will add an app-level attribute "x" to the class, corresponding to
    the interp-level attribute "w_x".

    This is just an annotation. The magic is done by W_Type.define(), which
    turns Member annotations into W_Member, which does its job thanks to the
    descriptor protocol.
    """
    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    @staticmethod
    def from_annotation(t: Any) -> Optional['Member']:
        """
        Return the Member instance found in the annotation metadata, if any.
        """
        for meta in getattr(t, '__metadata__', []):
            if isinstance(meta, Member):
                return meta
        return None


@BUILTINS.builtin_type('member', lazy_definition=True)
class W_Member(W_Object):
    """
    Descriptor object which turns interp-level fields (such as
    `w_obj.w_x`) into app-level properties (i.e. `obj.x`)
    """

    def __init__(self, name: str, field: str, w_type: W_Type) -> None:
        self.name = name
        self.field = field
        self.w_type = w_type

    def __repr__(self) -> str:
        n = self.name
        f = self.field
        T = self.w_type.fqn.human_name
        return f"<spy member '{n}: {T}'>"

    @builtin_method('__get__', color='blue', kind='metafunc')
    @staticmethod
    def w_GET(
        vm: 'SPyVM', wop_self: 'W_OpArg', wop_obj: 'W_OpArg'
    ) -> 'W_OpSpec':
        from spy.vm.opspec import W_OpSpec
        w_self = wop_self.w_blueval
        assert isinstance(w_self, W_Member)
        w_T = wop_obj.w_static_T
        field = w_self.field # the interp-level name of the attr (e.g, 'w_x')
        T = Annotated[W_Object, w_T]           # type of the object
        V = Annotated[W_Object, w_self.w_type] # type of the attribute

        @vm.register_builtin_func(w_T.fqn, f"__get_{w_self.name}__")
        def w_get(vm: 'SPyVM', w_obj: T) -> V:
            return getattr(w_obj, field)

        return W_OpSpec(w_get, [wop_obj])


    @builtin_method('__set__', color='blue', kind='metafunc')
    @staticmethod
    def w_set(
        vm: 'SPyVM', wop_self: 'W_OpArg', wop_obj: 'W_OpArg', wop_v: 'W_OpArg'
    ) -> 'W_OpSpec':
        from spy.vm.opspec import W_OpSpec
        w_self = wop_self.w_blueval
        assert isinstance(w_self, W_Member)
        w_T = wop_obj.w_static_T
        field = w_self.field # the interp-level name of the attr (e.g, 'w_x')
        T = Annotated[W_Object, w_T]           # type of the object
        V = Annotated[W_Object, w_self.w_type] # type of the attribute

        @vm.register_builtin_func(w_T.fqn, f"__set_{w_self.name}__")
        def w_set(vm: 'SPyVM', w_obj: T, w_val: V)-> None:
            setattr(w_obj, field, w_val)

        return W_OpSpec(w_set, [wop_obj, wop_v])
