from typing import TYPE_CHECKING, Any
from spy.fqn import QN
from spy.vm.object import W_Object, spytype, W_Type, W_Dynamic, W_I32
from spy.vm.function import spy_builtin
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

@spytype('ListFactory')
class W_ListFactory(W_Object):

    @staticmethod
    def op_GETITEM(vm: 'SPyVM', w_type: W_Type, w_vtype: W_Type) -> W_Dynamic:

        @spy_builtin(QN('operator::ListFactory_getitem'))
        def opimpl(vm: 'SPyVM', w_self: W_ListFactory, w_i: W_Type) -> W_Type:
            return make_W_List(vm, w_i)

        return vm.wrap(opimpl)


# XXX this should be marked as '@interp_blue' and cached automatically by the
# VM
CACHE = {}

def make_W_List(vm: 'SPyVM', w_T: W_Type) -> W_Type:
    T = w_T.pyclass
    key = (vm, w_T)
    if key in CACHE:
        return CACHE[key]

    tname = w_T.name
    name = f'list[{tname}]'

    @spytype(name)
    class W_List(W_Object):
        items_w: list[W_Object]

        def __init__(self, items_w: list[W_Object]):
            # XXX typecheck?
            self.items_w = items_w

        def spy_unwrap(self, vm: 'SPyVM') -> list[Any]:
            return [vm.unwrap(w_item) for w_item in self.items_w]

        @staticmethod
        def op_GETITEM(vm: 'SPyVM', w_listtype: W_Type,
                       w_itype: W_Type) -> W_Dynamic:
            @spy_builtin(QN('operator::list_getitem'))
            def list_getitem(vm: 'SPyVM', w_list: W_List, w_i: W_I32) -> T:
                i = vm.unwrap_i32(w_i)
                # XXX bound check?
                return w_list.items_w[i]
            return vm.wrap(list_getitem)

    w_result = vm.wrap(W_List)
    CACHE[key] = w_result
    return w_result
