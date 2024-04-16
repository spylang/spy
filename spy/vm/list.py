from typing import TYPE_CHECKING, Any
from spy.vm.object import W_Object, spytype
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@spytype('list')
class W_GenericList(W_Object):
    pass
