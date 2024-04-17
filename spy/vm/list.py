from typing import TYPE_CHECKING, Any
from spy.fqn import QN
from spy.vm.object import W_Object, spytype, W_Type, W_Dynamic
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


def make_W_List(vm: 'SPyVM', w_t: W_Type) -> W_Type:
    tname = w_t.name
    name = f'list[{tname}]'

    @spytype(name)
    class W_List(W_Object):
        pass

    return vm.wrap(W_List)
