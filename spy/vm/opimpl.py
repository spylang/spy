from typing import Annotated, Optional, ClassVar
from spy import ast
from spy.vm.object import Member, W_Type, W_Object, spytype
from spy.vm.function import W_Func
from spy.vm.list import W_List

@spytype('OpImpl')
class W_OpImpl(W_Object):
    NULL: ClassVar['W_OpImpl']
    _w_func: Optional[W_Func]

    def __init__(self, w_func: Optional[W_Func]) -> None:
        self._w_func = w_func

    def __repr__(self) -> str:
        if self._w_func is None:
            return f"<spy OpImpl NULL>"
        else:
            qn = self._w_func.qn
            return f"<spy OpImpl {qn}>"

    def is_null(self) -> bool:
        return self._w_func is None

    @property
    def w_func(self) -> W_Func:
        assert self._w_func is not None
        return self._w_func

    @property
    def w_restype(self) -> W_Type:
        return self.w_func.w_functype.w_restype


W_OpImpl.NULL = W_OpImpl(None)
