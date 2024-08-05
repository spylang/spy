from typing import TYPE_CHECKING, Any, no_type_check, Optional
from spy.fqn import QN
from spy.vm.object import (W_Object, spytype, W_Type, W_Dynamic, W_I32, W_Void,
                           W_Bool)
from spy.vm.sig import spy_builtin
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

@spytype('ListFactory')
class W_ListFactory(W_Object):
    __spy_storage_category__ = 'reference'

    @staticmethod
    def op_GETITEM(vm: 'SPyVM', w_type: W_Type, w_vtype: W_Type) -> W_Dynamic:
        return vm.wrap(make_list_type)



@spy_builtin(QN('__spy__::make_list_type'), color='blue')
def make_list_type(vm: 'SPyVM', w_self: W_ListFactory, w_T: W_Type) -> W_Type:
    """
    Create a concrete W_List class specialized for W_Type.
    """
    from spy.vm.b import B
    if w_T is B.w_type:
        return vm.wrap(W_List__W_Type)
    pyclass = _make_W_List(w_T)
    return vm.wrap(pyclass)  # type: ignore

class W_BaseList(W_Object):
    pass


def _make_W_List(w_T: W_Type) -> W_Type:
    """
    DON'T CALL THIS DIRECTLY!
    You should call make_list_type instead, which knows how to deal with
    "well-known lists".
    """
    T = w_T.pyclass
    app_name = f'list[{w_T.name}]'        # e.g. list[i32]
    interp_name = f'W_List[{T.__name__}]' # e.g. W_List[W_I32]

    @spytype(app_name)
    class W_List(W_BaseList):
        items_w: list[W_Object]

        def __init__(self, items_w: list[W_Object]):
            # XXX typecheck?
            self.items_w = items_w

        def __repr__(self):
            cls = self.__class__.__name__
            return f'{cls}({self.items_w})'

        def spy_unwrap(self, vm: 'SPyVM') -> list[Any]:
            return [vm.unwrap(w_item) for w_item in self.items_w]

        @staticmethod
        def op_GETITEM(vm: 'SPyVM', w_listtype: W_Type,
                       w_itype: W_Type) -> W_Dynamic:
            @no_type_check
            @spy_builtin(QN('operator::list_getitem'))
            def getitem(vm: 'SPyVM', w_list: W_List, w_i: W_I32) -> T:
                i = vm.unwrap_i32(w_i)
                # XXX bound check?
                return w_list.items_w[i]
            return vm.wrap(getitem)

        @staticmethod
        def op_SETITEM(vm: 'SPyVM', w_listtype: W_Type, w_itype: W_Type,
                       w_vtype: W_Type) -> W_Dynamic:
            from spy.vm.b import B

            @no_type_check
            @spy_builtin(QN('operator::list_setitem'))
            def setitem(vm: 'SPyVM', w_list: W_List, w_i: W_I32,
                        w_v: T) -> W_Void:
                assert isinstance(w_v, T)
                i = vm.unwrap_i32(w_i)
                # XXX bound check?
                w_list.items_w[i] = w_v
                return B.w_None
            return vm.wrap(setitem)

        @staticmethod
        def op_EQ(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_Dynamic:
            from spy.vm.b import B
            assert w_ltype.pyclass is W_List

            @no_type_check
            @spy_builtin(QN('operator::list_eq'))
            def eq(vm: 'SPyVM', w_l1: W_List, w_l2: W_List) -> W_Bool:
                items1_w = w_l1.items_w
                items2_w = w_l2.items_w
                if len(items1_w) != len(items2_w):
                    return B.w_False
                for w_1, w_2 in zip(items1_w, items2_w):
                    if vm.is_False(vm.eq(w_1, w_2)):
                        return B.w_False
                return B.w_True

            if w_ltype is w_rtype:
                return vm.wrap(eq)
            else:
                return B.w_NotImplemented

    W_List.__name__ = W_List.__qualname__ = interp_name
    return W_List        # type: ignore


# well-known list types
W_List__W_Type = _make_W_List(W_Type._w)
