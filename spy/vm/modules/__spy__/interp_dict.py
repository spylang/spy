from typing import TYPE_CHECKING, Annotated, Any, Generic, Self, TypeVar

from spy.errors import SPyError
from spy.fqn import FQN
from spy.vm.b import OP, B
from spy.vm.builtin import builtin_method
from spy.vm.modules.__spy__ import SPY
from spy.vm.object import W_Object, W_Type
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.primitive import W_I32, W_Bool
from spy.vm.str import W_Str

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@B.builtin_func(color="blue", kind="generic")
def w_make_interp_dict_type(vm: "SPyVM", w_K: W_Type, w_V: W_Type) -> W_Type:
    """
    Create a W_InterpDictType specialized K, V.
    """
    fqn = FQN("__spy__").join("interp_dict", [w_K.fqn, w_V.fqn])
    w_dictT = W_InterpDictType.from_types(fqn, w_K, w_V)
    w_dictT.register_push_function(vm)
    return w_dictT


@SPY.builtin_type("InterpDictType")
class W_InterpDictType(W_Type):
    """
    A specialized dict type.
    interp_dict[str, i32] -> W_InterpDictType(fqn, B.w_str, B.w_i32)
    """

    w_keyT: W_Type
    w_valueT: W_Type

    @classmethod
    def from_types(cls, fqn: FQN, w_keyT: W_Type, w_valueT: W_Type) -> Self:
        w_T = cls.from_pyclass(fqn, W_InterpDict)
        w_T.w_keyT = w_keyT
        w_T.w_valueT = w_valueT
        return w_T

    def register_push_function(self, vm: "SPyVM") -> None:
        w_dictT = self
        w_K = w_dictT.w_keyT
        w_V = w_dictT.w_valueT
        DICT = Annotated[W_InterpDict, w_dictT]
        K = Annotated[W_Object, w_K]
        V = Annotated[W_Object, w_V]

        @vm.register_builtin_func(w_dictT.fqn)
        def w__push(vm: "SPyVM", w_dict: DICT, w_key: K, w_value: V) -> DICT:
            key = w_key.spy_key(vm)
            w_dict.items_w[key] = (w_key, w_value)
            return w_dict


@SPY.builtin_type("MetaBaseInterpDict")
class W_MetaBaseInterpDict(W_Type):
    """
    This exists solely to be able to do interp_dict[K, V]
    """

    @builtin_method("__getitem__", color="blue", kind="metafunc")
    @staticmethod
    def w_GETITEM(
        vm: "SPyVM", wam_obj: W_MetaArg, wam_K: W_MetaArg, wam_V: W_MetaArg
    ) -> W_OpSpec:
        return W_OpSpec(w_make_interp_dict_type, [wam_K, wam_V])


@SPY.builtin_type("interp_dict", W_MetaClass=W_MetaBaseInterpDict)
class W_BaseInterpDict(W_Object):
    """
    The 'interp_dict' type.

    It's the base type for all interp dicts. In other words, `interp_dict[str, i32]`
    inherits from `interp_dict`.

    The specialized types are created by calling the builtin make_interp_dict_type:
    see its docstring for details.
    """

    def __init__(self, items_w: Any) -> None:
        raise Exception("You cannot instantiate W_BaseInterpDict, use W_InterpDict")


K = TypeVar("K", bound="W_Object")
V = TypeVar("V", bound="W_Object")


class W_InterpDict(W_BaseInterpDict, Generic[K, V]):
    """
    An instance of interp_dict.

    Internally it's implemented as an interp-level dict which maps `spy_key()` to tuples
    `(key, value)`
    """

    w_dictT: W_InterpDictType
    items_w: dict[Any, tuple[K, V]]

    def __init__(
        self,
        w_dictT: W_InterpDictType,
        items_w: dict[Any, tuple[W_Object, W_Object]],
    ) -> None:
        assert isinstance(w_dictT, W_InterpDictType)
        self.w_dictT = w_dictT
        self.items_w = items_w  # type: ignore

    def __repr__(self) -> str:
        cls = self.__class__.__name__
        K = self.w_dictT.w_keyT.fqn.human_name
        V = self.w_dictT.w_valueT.fqn.human_name
        return f"{cls}('{K}', '{V}', {self.items_w})"

    def spy_get_w_type(self, vm: "SPyVM") -> W_Type:
        return self.w_dictT

    def spy_unwrap(self, vm: "SPyVM") -> dict[Any, Any]:
        return {vm.unwrap(w_k): vm.unwrap(w_v) for w_k, w_v in self.items_w.values()}

    @staticmethod
    def _get_dicttype(wam_dict: W_MetaArg) -> W_InterpDictType:
        w_dictT = wam_dict.w_static_T
        if isinstance(w_dictT, W_InterpDictType):
            return w_dictT
        else:
            assert False, "FIXME: raise a nice error"

    @builtin_method("__new__", color="blue", kind="metafunc")
    @staticmethod
    def w_NEW(vm: "SPyVM", wam_T: W_MetaArg, *args_wam: W_MetaArg) -> W_OpSpec:
        w_dictT = wam_T.w_blueval
        assert isinstance(w_dictT, W_InterpDictType)
        w_K = w_dictT.w_keyT
        w_V = w_dictT.w_valueT
        DICT = Annotated[W_InterpDict, w_dictT]

        @vm.register_builtin_func(w_dictT.fqn)
        def w_new(vm: "SPyVM") -> DICT:
            return W_InterpDict(w_dictT, {})

        return W_OpSpec(w_new, [])

    @builtin_method("__convert_from__", color="blue", kind="metafunc")
    @staticmethod
    def w_CONVERT_TO(
        vm: "SPyVM",
        wam_expT: W_MetaArg,
        wam_gotT: W_MetaArg,
        wam_obj: W_MetaArg,
    ) -> W_OpSpec:
        w_expT = wam_expT.w_blueval
        w_gotT = wam_gotT.w_blueval
        assert isinstance(w_expT, W_Type)

        if w_gotT is SPY.w_EmptyDictType:
            DICT = Annotated[W_Object, w_expT]

            @vm.register_builtin_func(w_expT.fqn)
            def w_new_empty(vm: "SPyVM") -> DICT:
                return vm.call_w(w_expT, [])

            return W_OpSpec(w_new_empty, [])

        return W_OpSpec.NULL

    @builtin_method("__getitem__", color="blue", kind="metafunc")
    @staticmethod
    def w_GETITEM(vm: "SPyVM", wam_dict: W_MetaArg, wam_key: W_MetaArg) -> W_OpSpec:
        w_dictT = W_InterpDict._get_dicttype(wam_dict)
        w_K = w_dictT.w_keyT
        w_V = w_dictT.w_valueT
        DICT = Annotated[W_InterpDict, w_dictT]
        K = Annotated[W_Object, w_K]
        V = Annotated[W_Object, w_V]

        @vm.register_builtin_func(w_dictT.fqn)
        def w_getitem(vm: "SPyVM", w_dict: DICT, w_key: K) -> V:
            key = w_key.spy_key(vm)
            if key in w_dict.items_w:
                _, w_value = w_dict.items_w[key]
                return w_value
            else:
                raise SPyError("W_KeyError", f"key not found")

        return W_OpSpec(w_getitem)

    @builtin_method("__setitem__", color="blue", kind="metafunc")
    @staticmethod
    def w_SETITEM(
        vm: "SPyVM", wam_dict: W_MetaArg, wam_key: W_MetaArg, wam_val: W_MetaArg
    ) -> W_OpSpec:
        w_dictT = W_InterpDict._get_dicttype(wam_dict)
        w_K = w_dictT.w_keyT
        w_V = w_dictT.w_valueT
        DICT = Annotated[W_InterpDict, w_dictT]
        K = Annotated[W_Object, w_K]
        V = Annotated[W_Object, w_V]

        @vm.register_builtin_func(w_dictT.fqn)
        def w_setitem(vm: "SPyVM", w_dict: DICT, w_key: K, w_val: V) -> None:
            key = w_key.spy_key(vm)
            w_dict.items_w[key] = (w_key, w_val)

        return W_OpSpec(w_setitem)

    @builtin_method("__eq__", color="blue", kind="metafunc")
    @staticmethod
    def w_EQ(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpSpec:
        w_ltype = wam_l.w_static_T
        w_rtype = wam_r.w_static_T
        if w_ltype is not w_rtype:
            return W_OpSpec.NULL
        w_dictT = W_InterpDict._get_dicttype(wam_l)
        DICT = Annotated[W_InterpDict, w_dictT]

        @vm.register_builtin_func(w_dictT.fqn)
        def w_eq(vm: "SPyVM", w_d1: DICT, w_d2: DICT) -> W_Bool:
            items1_w = w_d1.items_w
            items2_w = w_d2.items_w
            if len(items1_w) != len(items2_w):
                return B.w_False
            for key, (w_k1, w_v1) in items1_w.items():
                if key not in items2_w:
                    return B.w_False
                w_k2, w_v2 = items2_w[key]
                if vm.is_False(vm.eq_w(w_v1, w_v2)):
                    return B.w_False
            return B.w_True

        return W_OpSpec(w_eq)

    @builtin_method("__len__", color="blue", kind="metafunc")
    @staticmethod
    def w_LEN(vm: "SPyVM", wam_dict: W_MetaArg) -> W_OpSpec:
        w_dictT = W_InterpDict._get_dicttype(wam_dict)
        DICT = Annotated[W_InterpDict, w_dictT]

        @vm.register_builtin_func(w_dictT.fqn)
        def w_len(vm: "SPyVM", w_dict: DICT) -> W_I32:
            return vm.wrap(len(w_dict.items_w))

        return W_OpSpec(w_len)

    def _repr(self, vm: "SPyVM") -> W_Str:
        if len(self.items_w) == 0:
            return vm.wrap("{}")

        parts = []
        for w_k, w_v in self.items_w.values():
            if self.w_dictT.w_keyT is B.w_str:
                k_str = vm.unwrap_str(w_k)
                k_repr = repr(k_str)
            else:
                k_repr = vm.unwrap_str(vm.str_w(w_k))

            if self.w_dictT.w_valueT is B.w_str:
                v_str = vm.unwrap_str(w_v)
                v_repr = repr(v_str)
            else:
                v_repr = vm.unwrap_str(vm.str_w(w_v))

            parts.append(f"{k_repr}: {v_repr}")
        return vm.wrap("{" + ", ".join(parts) + "}")

    @builtin_method("__str__", color="blue", kind="metafunc")
    @staticmethod
    def w_STR(vm: "SPyVM", wam_dict: W_MetaArg) -> W_OpSpec:
        w_dictT = W_InterpDict._get_dicttype(wam_dict)
        DICT = Annotated[W_InterpDict, w_dictT]

        @vm.register_builtin_func(w_dictT.fqn)
        def w_str(vm: "SPyVM", w_dict: DICT) -> W_Str:
            return w_dict._repr(vm)

        return W_OpSpec(w_str, [wam_dict])

    @builtin_method("__repr__", color="blue", kind="metafunc")
    @staticmethod
    def w_REPR(vm: "SPyVM", wam_dict: W_MetaArg) -> W_OpSpec:
        w_dictT = W_InterpDict._get_dicttype(wam_dict)
        DICT = Annotated[W_InterpDict, w_dictT]

        @vm.register_builtin_func(w_dictT.fqn)
        def w_repr(vm: "SPyVM", w_dict: DICT) -> W_Str:
            return w_dict._repr(vm)

        return W_OpSpec(w_repr, [wam_dict])

    @builtin_method("_push", color="blue", kind="metafunc")
    @staticmethod
    def w__PUSH(
        vm: "SPyVM", wam_dict: W_MetaArg, wam_key: W_MetaArg, wam_val: W_MetaArg
    ) -> W_OpSpec:
        w_dictT = W_InterpDict._get_dicttype(wam_dict)
        w_K = w_dictT.w_keyT
        w_V = w_dictT.w_valueT
        DICT = Annotated[W_InterpDict, w_dictT]
        K = Annotated[W_Object, w_K]
        V = Annotated[W_Object, w_V]

        @vm.register_builtin_func(w_dictT.fqn)
        def w_push(vm: "SPyVM", w_dict: DICT, w_key: K, w_val: V) -> DICT:
            key = w_key.spy_key(vm)
            w_dict.items_w[key] = (w_key, w_val)
            return w_dict

        return W_OpSpec(w_push)
