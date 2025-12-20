from typing import TYPE_CHECKING, Annotated, Any, Generic, Self, TypeVar

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

# PREBUILT list types are instantiated the end of the file
PREBUILT_INTERP_LIST_TYPES: dict[W_Type, "W_InterpListType"] = {}


def _make_interp_list_type(w_T: W_Type) -> "W_InterpListType":
    fqn = FQN("__spy__").join("interp_list", [w_T.fqn])  # builtins::interp_list[i32]
    return W_InterpListType.from_itemtype(fqn, w_T)


@B.builtin_func(color="blue", kind="generic")
def w_make_interp_list_type(vm: "SPyVM", w_T: W_Type) -> W_Type:
    """
    Create a concrete W_List class specialized for W_Type.

    Given a type T, it is always safe to call make_interp_list_type(T) multiple
    types, and it is guaranteed to get always the same type.

    It is worth noting that to achieve that, we have two layers of caching:

      - if we have a prebuilt list type, just use that
      - for other types, we rely on the fact that `make_interp_list_type` is blue.
    """
    if w_T in PREBUILT_INTERP_LIST_TYPES:
        return PREBUILT_INTERP_LIST_TYPES[w_T]
    w_listtype = _make_interp_list_type(w_T)

    # register the _push function which is used by ASTFrame.eval_expr_List.
    # NOTE: for PREBUILT_INTERP_LIST_TYPES, we do it inside __spy__.__INIT__, because we
    # don't have a vm earlier.
    w_listtype.register_push_function(vm)
    return w_listtype


@SPY.builtin_type("InterpListType")
class W_InterpListType(W_Type):
    """
    A specialized list type.
    interp_list[i32] -> W_InterpListType(fqn, B.w_i32)
    """

    w_itemtype: W_Type

    @classmethod
    def from_itemtype(cls, fqn: FQN, w_itemtype: W_Type) -> Self:
        w_T = cls.from_pyclass(fqn, W_InterpList)
        w_T.w_itemtype = w_itemtype
        return w_T

    def register_push_function(self, vm: "SPyVM") -> None:
        w_listtype = self
        w_T = w_listtype.w_itemtype
        LIST = Annotated[W_InterpList, w_listtype]
        T = Annotated[W_Object, w_T]

        @vm.register_builtin_func(w_listtype.fqn)
        def w__push(vm: "SPyVM", w_list: LIST, w_item: T) -> LIST:
            w_list.items_w.append(w_item)
            return w_list


@SPY.builtin_type("MetaBaseInterpList")
class W_MetaBaseInterpList(W_Type):
    """
    This exist solely to be able to do interp_list[...]
    """

    @builtin_method("__getitem__", color="blue", kind="metafunc")
    @staticmethod
    def w_GETITEM(vm: "SPyVM", wam_obj: W_MetaArg, wam_T: W_MetaArg) -> W_OpSpec:
        from spy.vm.opspec import W_OpSpec

        return W_OpSpec(w_make_interp_list_type, [wam_T])


@SPY.builtin_type("interp_list", W_MetaClass=W_MetaBaseInterpList)
class W_BaseInterpList(W_Object):
    """
    The 'interp_list' type.

    It's the base type for all interp lists.  In other words, `interp_list[i32]`
    inherits from `interp_list`.

    The specialized types are created by calling the builtin make_interp_list_type:
    see its docstring for details.
    """

    def __init__(self, items_w: Any) -> None:
        raise Exception("You cannot instantiate W_BaseInterpList, use W_InterpList")


T = TypeVar("T", bound="W_Object")


class W_InterpList(W_BaseInterpList, Generic[T]):
    w_listtype: W_InterpListType
    items_w: list[T]

    def __init__(self, w_listtype: W_InterpListType, items_w: list[W_Object]) -> None:
        assert isinstance(w_listtype, W_InterpListType)
        self.w_listtype = w_listtype
        # XXX we should do a proper typecheck, but let's at least do a sanity check
        if len(items_w) > 0:
            assert isinstance(items_w[0], W_Object)
        self.items_w = items_w  # type: ignore

    def __repr__(self) -> str:
        cls = self.__class__.__name__
        T = self.w_listtype.w_itemtype.fqn.human_name
        return f"{cls}('{T}', {self.items_w})"

    def spy_get_w_type(self, vm: "SPyVM") -> W_Type:
        return self.w_listtype

    def spy_unwrap(self, vm: "SPyVM") -> list[Any]:
        return [vm.unwrap(w_item) for w_item in self.items_w]

    @staticmethod
    def _get_listtype(wam_list: W_MetaArg) -> W_InterpListType:
        w_listtype = wam_list.w_static_T
        if isinstance(w_listtype, W_InterpListType):
            return w_listtype
        else:
            # I think we can get here if we have something typed 'list' as
            # opposed to e.g. 'list[i32]'
            assert False, "FIXME: raise a nice error"

    @builtin_method("__new__", color="blue", kind="metafunc")
    @staticmethod
    def w_NEW(vm: "SPyVM", wam_T: W_MetaArg, *args_wam: W_MetaArg) -> W_OpSpec:
        w_listtype = wam_T.w_blueval
        assert isinstance(w_listtype, W_InterpListType)
        w_T = w_listtype.w_itemtype
        LIST = Annotated[W_InterpList, w_listtype]
        T = Annotated[W_Object, w_T]

        @vm.register_builtin_func(w_listtype.fqn)
        def w_new(vm: "SPyVM", *args_w: T) -> LIST:
            return W_InterpList(w_listtype, list(args_w))

        return W_OpSpec(w_new, list(args_wam))

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

        if w_gotT is SPY.w_EmptyListType:
            LIST = Annotated[W_Object, w_expT]

            @vm.register_builtin_func(w_expT.fqn)
            def w_new_empty(vm: "SPyVM") -> LIST:
                return vm.call_w(w_expT, [])

            return W_OpSpec(w_new_empty, [])

        return W_OpSpec.NULL

    @builtin_method("__getitem__", color="blue", kind="metafunc")
    @staticmethod
    def w_GETITEM(vm: "SPyVM", wam_list: W_MetaArg, wam_i: W_MetaArg) -> W_OpSpec:
        w_listtype = W_InterpList._get_listtype(wam_list)
        w_T = w_listtype.w_itemtype
        LIST = Annotated[W_InterpList, w_listtype]
        T = Annotated[W_Object, w_T]

        @vm.register_builtin_func(w_listtype.fqn)
        def w_getitem(vm: "SPyVM", w_list: LIST, w_i: W_I32) -> T:
            i = vm.unwrap_i32(w_i)
            # XXX bound check?
            return w_list.items_w[i]

        return W_OpSpec(w_getitem)

    @builtin_method("__setitem__", color="blue", kind="metafunc")
    @staticmethod
    def w_SETITEM(
        vm: "SPyVM", wam_list: W_MetaArg, wam_i: W_MetaArg, wam_v: W_MetaArg
    ) -> W_OpSpec:
        from spy.vm.opspec import W_OpSpec

        w_listtype = W_InterpList._get_listtype(wam_list)
        w_T = w_listtype.w_itemtype
        LIST = Annotated[W_InterpList, w_listtype]
        T = Annotated[W_Object, w_T]

        @vm.register_builtin_func(w_listtype.fqn)
        def w_setitem(vm: "SPyVM", w_list: LIST, w_i: W_I32, w_v: T) -> None:
            i = vm.unwrap_i32(w_i)
            # XXX bound check?
            w_list.items_w[i] = w_v

        return W_OpSpec(w_setitem)

    @builtin_method("__eq__", color="blue", kind="metafunc")
    @staticmethod
    def w_EQ(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpSpec:
        from spy.vm.opspec import W_OpSpec

        w_ltype = wam_l.w_static_T
        w_rtype = wam_r.w_static_T
        if w_ltype is not w_rtype:
            return W_OpSpec.NULL
        w_listtype = W_InterpList._get_listtype(wam_l)
        LIST = Annotated[W_InterpList, w_listtype]

        @vm.register_builtin_func(w_listtype.fqn)
        def w_eq(vm: "SPyVM", w_l1: LIST, w_l2: LIST) -> W_Bool:
            items1_w = w_l1.items_w
            items2_w = w_l2.items_w
            if len(items1_w) != len(items2_w):
                return B.w_False
            for w_1, w_2 in zip(items1_w, items2_w):
                if vm.is_False(vm.eq_w(w_1, w_2)):
                    return B.w_False
            return B.w_True

        return W_OpSpec(w_eq)

    @builtin_method("__add__", color="blue", kind="metafunc")
    @staticmethod
    def w_ADD(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpSpec:
        from spy.vm.opspec import W_OpSpec

        w_ltype = wam_l.w_static_T
        w_rtype = wam_r.w_static_T
        if w_ltype is not w_rtype:
            return W_OpSpec.NULL
        w_listtype = W_InterpList._get_listtype(wam_l)
        LIST = Annotated[W_InterpList, w_listtype]

        @vm.register_builtin_func(w_listtype.fqn)
        def w_add(vm: "SPyVM", w_l1: LIST, w_l2: LIST) -> LIST:
            return W_InterpList(w_listtype, w_l1.items_w + w_l2.items_w)

        return W_OpSpec(w_add)

    def _repr(self, vm: "SPyVM") -> W_Str:
        if self.w_listtype.w_itemtype is B.w_str:
            # special case list[str]
            parts = [vm.unwrap_str(w_item) for w_item in self.items_w]
            return vm.wrap(str(parts))
        else:
            parts = [vm.unwrap_str(vm.str_w(w_obj)) for w_obj in self.items_w]
            return vm.wrap("[" + ", ".join(parts) + "]")

    @builtin_method("__str__", color="blue", kind="metafunc")
    @staticmethod
    def w_STR(vm: "SPyVM", wam_list: W_MetaArg) -> W_OpSpec:
        w_listtype = W_InterpList._get_listtype(wam_list)
        w_T = w_listtype.w_itemtype
        LIST = Annotated[W_InterpList, w_listtype]

        @vm.register_builtin_func(w_listtype.fqn)
        def w_str(vm: "SPyVM", w_lst: LIST) -> W_Str:
            return w_lst._repr(vm)

        return W_OpSpec(w_str, [wam_list])

    @builtin_method("__repr__", color="blue", kind="metafunc")
    @staticmethod
    def w_REPR(vm: "SPyVM", wam_list: W_MetaArg) -> W_OpSpec:
        w_listtype = W_InterpList._get_listtype(wam_list)
        w_T = w_listtype.w_itemtype
        LIST = Annotated[W_InterpList, w_listtype]

        @vm.register_builtin_func(w_listtype.fqn)
        def w_repr(vm: "SPyVM", w_lst: LIST) -> W_Str:
            return w_lst._repr(vm)

        return W_OpSpec(w_repr, [wam_list])


# prebuilt list types
# ===================

w_str_interp_list_type = _make_interp_list_type(B.w_str)
w_metaarg_interp_list_type = _make_interp_list_type(OP.w_MetaArg)

PREBUILT_INTERP_LIST_TYPES[B.w_str] = w_str_interp_list_type
PREBUILT_INTERP_LIST_TYPES[OP.w_MetaArg] = w_metaarg_interp_list_type

W_StrInterpList = Annotated[W_InterpList[W_Str], w_str_interp_list_type]
W_MetaArgInterpList = Annotated[W_InterpList[W_MetaArg], w_metaarg_interp_list_type]


def make_str_interp_list(items_w: list[W_Str]) -> W_StrInterpList:
    return W_InterpList(w_str_interp_list_type, items_w)  # type: ignore


def make_metaarg_interp_list(args_wam: list[W_MetaArg]) -> W_MetaArgInterpList:
    return W_InterpList(w_metaarg_interp_list_type, args_wam)  # type: ignore
