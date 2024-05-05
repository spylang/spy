from typing import TYPE_CHECKING, Any, no_type_check, Optional
from spy.fqn import QN
from spy.vm.object import W_Object, spytype, W_Type, W_Dynamic, W_I32, W_Void
from spy.vm.sig import spy_builtin
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

@spytype('ListFactory')
class W_ListFactory(W_Object):

    @staticmethod
    def op_GETITEM(vm: 'SPyVM', w_type: W_Type, w_vtype: W_Type) -> W_Dynamic:

        @spy_builtin(QN('operator::ListFactory_getitem'))
        def opimpl(vm: 'SPyVM', w_self: W_ListFactory, w_i: W_Type) -> W_Type:
            pyclass = make_W_List(vm, w_i)
            return vm.wrap(pyclass)  # type: ignore

        return vm.wrap(opimpl)

class W_BaseList(W_Object):
    pass

# XXX this should be marked as '@interp_blue' and cached automatically by the
# VM
CACHE: dict[Any, W_Type] = {}

def make_W_List(vm_cache: Optional['SPyVM'], w_T: W_Type) -> W_Type:
    # well-known specialized lists exist independently of the VM
    ## if w_T in (W_Type, W_I32):
    ##     vm_cache = None

    vm_cache = None #XXX


    T = w_T.pyclass
    key = (vm_cache, w_T)
    if key in CACHE:
        return CACHE[key]

    tname = w_T.name
    name = f'list[{tname}]'

    @spytype(name)
    class W_List(W_BaseList):
        items_w: list[W_Object]

        def __init__(self, items_w: list[W_Object]):
            # XXX typecheck?
            self.items_w = items_w

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

    W_List.__name__ = f'W_List[{T.__name__}]'
    CACHE[key] = W_List  # type: ignore
    return W_List        # type: ignore


W_List__W_Type = make_W_List(None, W_Type._w)
