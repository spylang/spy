from typing import (TYPE_CHECKING, Any, TypeVar, Generic, Annotated, Self)
from spy.fqn import FQN
from spy.vm.b import B, OP, BUILTINS
from spy.vm.primitive import W_I32, W_Bool
from spy.vm.object import W_Object, W_Type
from spy.vm.opspec import W_OpSpec, W_MetaArg
from spy.vm.builtin import builtin_method
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@B.builtin_type('ListType')
class W_ListType(W_Type):
    """
    A specialized list type.
    list[i32] -> W_ListType(fqn, B.w_i32)
    """
    w_itemtype: W_Type

    @classmethod
    def from_itemtype(cls, fqn: FQN, w_itemtype: W_Type) -> Self:
        w_T = cls.from_pyclass(fqn, W_List)
        w_T.w_itemtype = w_itemtype
        return w_T


# PREBUILT list types are instantiated the end of the file
PREBUILT_LIST_TYPES: dict[W_Type, W_ListType] = {}

@BUILTINS.builtin_func(color='blue', hidden=True)
def w_make_list_type(vm: 'SPyVM', w_list: W_Object, w_T: W_Type) -> W_ListType:
    """
    Create a concrete W_List class specialized for W_Type.

    Given a type T, it is always safe to call make_list_type(T) multiple
    types, and it is guaranteed to get always the same type.

    It is worth noting that to achieve that, we have two layers of caching:

      - if we have a prebuilt list type, just use that
      - for other types, we rely on the fact that `make_list_type` is blue.
    """
    if w_T in PREBUILT_LIST_TYPES:
        return PREBUILT_LIST_TYPES[w_T]
    return _make_list_type(w_T)

def _make_list_type(w_T: W_Type) -> W_ListType:
    fqn = FQN('builtins').join('list', [w_T.fqn])  # builtins::list[i32]
    return W_ListType.from_itemtype(fqn, w_T)

@B.builtin_type('MetaBaseList')
class W_MetaBaseList(W_Type):
    """
    This exist solely to be able to do list[...]
    """

    @builtin_method('__getitem__', color='blue', kind='metafunc')
    @staticmethod
    def w_GETITEM(vm: 'SPyVM', wam_obj: W_MetaArg, wam_i: W_MetaArg) -> W_OpSpec:
        from spy.vm.opspec import W_OpSpec
        return W_OpSpec(w_make_list_type)


@B.builtin_type('list', W_MetaClass=W_MetaBaseList)
class W_BaseList(W_Object):
    """
    The 'list' type.

    It's the base type for all lists.  In other words, `list[i32]` inherits
    from `list`.

    The specialized types are created by calling the builtin make_list_type:
    see its docstring for details.
    """

    def __init__(self, items_w: Any) -> None:
        raise Exception("You cannot instantiate W_BaseList, use W_List")



T = TypeVar('T', bound='W_Object')

class W_List(W_BaseList, Generic[T]):
    w_listtype: W_ListType
    items_w: list[T]

    def __init__(self, w_listtype: W_ListType, items_w: list[W_Object]) -> None:
        assert isinstance(w_listtype, W_ListType)
        self.w_listtype = w_listtype
        # XXX typecheck?
        self.items_w = items_w  # type: ignore

    def __repr__(self) -> str:
        cls = self.__class__.__name__
        T = self.w_listtype.w_itemtype.fqn.human_name
        return f"{cls}('{T}', {self.items_w})"

    def spy_get_w_type(self, vm: 'SPyVM') -> W_Type:
        return self.w_listtype

    def spy_unwrap(self, vm: 'SPyVM') -> list[Any]:
        return [vm.unwrap(w_item) for w_item in self.items_w]

    @staticmethod
    def _get_listtype(wam_list: W_MetaArg) -> W_ListType:
        w_listtype = wam_list.w_static_T
        if isinstance(w_listtype, W_ListType):
            return w_listtype
        else:
            # I think we can get here if we have something typed 'list' as
            # opposed to e.g. 'list[i32]'
            assert False, 'FIXME: raise a nice error'

    @builtin_method('__getitem__', color='blue', kind='metafunc')
    @staticmethod
    def w_GETITEM(vm: 'SPyVM', wam_list: W_MetaArg, wam_i: W_MetaArg) -> W_OpSpec:
        from spy.vm.opspec import W_OpSpec
        w_listtype = W_List._get_listtype(wam_list)
        w_T = w_listtype.w_itemtype
        LIST = Annotated[W_List, w_listtype]
        T = Annotated[W_Object, w_T]

        @vm.register_builtin_func(w_listtype.fqn)
        def w_getitem(vm: 'SPyVM', w_list: LIST, w_i: W_I32) -> T:
            i = vm.unwrap_i32(w_i)
            # XXX bound check?
            return w_list.items_w[i]
        return W_OpSpec(w_getitem)

    @builtin_method('__setitem__', color='blue', kind='metafunc')
    @staticmethod
    def w_SETITEM(vm: 'SPyVM', wam_list: W_MetaArg, wam_i: W_MetaArg,
                  wam_v: W_MetaArg) -> W_OpSpec:
        from spy.vm.opspec import W_OpSpec
        w_listtype = W_List._get_listtype(wam_list)
        w_T = w_listtype.w_itemtype
        LIST = Annotated[W_List, w_listtype]
        T = Annotated[W_Object, w_T]

        @vm.register_builtin_func(w_listtype.fqn)
        def w_setitem(vm: 'SPyVM', w_list: LIST, w_i: W_I32, w_v: T) -> None:
            i = vm.unwrap_i32(w_i)
            # XXX bound check?
            w_list.items_w[i] = w_v
        return W_OpSpec(w_setitem)

    @builtin_method('__eq__', color='blue', kind='metafunc')
    @staticmethod
    def w_EQ(vm: 'SPyVM', wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpSpec:
        from spy.vm.opspec import W_OpSpec
        w_ltype = wam_l.w_static_T
        w_rtype = wam_r.w_static_T
        if w_ltype is not w_rtype:
            return W_OpSpec.NULL
        w_listtype = W_List._get_listtype(wam_l)
        LIST = Annotated[W_List, w_listtype]

        @vm.register_builtin_func(w_listtype.fqn)
        def w_eq(vm: 'SPyVM', w_l1: LIST, w_l2: LIST) -> W_Bool:
            items1_w = w_l1.items_w
            items2_w = w_l2.items_w
            if len(items1_w) != len(items2_w):
                return B.w_False
            for w_1, w_2 in zip(items1_w, items2_w):
                if vm.is_False(vm.eq(w_1, w_2)):
                    return B.w_False
            return B.w_True
        return W_OpSpec(w_eq)


# prebuilt list types
# ===================

# This it is no longer used in the current state, but the code is kept around
# in case it's needed in the future.
#
# The following commented-out code makes an interp-level type W_MetaArgList
# which corresponds to the interp-level type `list[OpArg]`.

w_metaarg_list_type = _make_list_type(OP.w_MetaArg)
PREBUILT_LIST_TYPES[OP.w_MetaArg] = w_metaarg_list_type

W_MetaArgList = Annotated[W_List[W_MetaArg], w_metaarg_list_type]
def make_metaarg_list(args_wam: list[W_MetaArg]) -> W_MetaArgList:
   return W_List(w_metaarg_list_type, args_wam)  # type: ignore
