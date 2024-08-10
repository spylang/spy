from typing import Annotated, Optional, ClassVar
from spy import ast
from spy.vm.object import Member, W_Type, W_Object, spytype
from spy.vm.function import W_Func

@spytype('AbVal')
class W_AbsVal(W_Object):
    """
    Abstract Value.

    XXX explain.
    """
    w_static_type: Annotated[W_Type, Member('static_type')]
    expr: ast.Expr

    def __init__(self, w_type: W_Type, expr: ast.Expr) -> None:
        self.w_type = w_type
        self.expr = expr

@spytype('OpImpl')
class W_OpImpl(W_Object):
    NULL: ClassVar['W_OpImpl']
    _w_func: Optional[W_Func]
    _args_w: Optional[list[W_AbsVal]]

    def __init__(self, *args) -> None:
        raise NotImplementedError('Please use W_OpImpl.simple()')

    @classmethod
    def simple(cls, w_func: W_Func) -> 'W_OpImpl':
        w_opimpl = cls.__new__(cls)
        w_opimpl._w_func = w_func
        w_opimpl._args_w = None
        return w_opimpl

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


W_OpImpl.NULL = W_OpImpl.simple(None)
