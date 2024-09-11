from typing import Annotated, Optional, ClassVar, no_type_check
from spy import ast
from spy.fqn import QN
from spy.location import Loc
from spy.vm.object import Member, W_Type, W_Object, spytype, W_Bool
from spy.vm.function import W_Func
from spy.vm.sig import spy_builtin

@spytype('Value')
class W_Value(W_Object):
    """
    A Value represent an operand of an OPERATOR.

    The naming convention is wv_one and manyvalues_wv.
    """
    name: str
    i: int
    w_static_type: Annotated[W_Type, Member('static_type')]
    loc: Optional[Loc]

    def __init__(self, name: str, i: int, w_static_type: W_Type,
                 loc: Optional[Loc]) -> None:
        self.name = name
        self.i = i
        self.w_static_type = w_static_type
        self.loc = loc

    def __repr__(self):
        return f'<W_Value {self.name}{self.i}: {self.w_static_type.name}>'

    @staticmethod
    def op_EQ(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> 'W_OpImpl':
        from spy.vm.b import B
        assert w_ltype.pyclass is W_Value

        @no_type_check
        @spy_builtin(QN('operator::value_eq'))
        def eq(vm: 'SPyVM', wv1: W_Value, wv2: W_Value) -> W_Bool:
            # note that the name is NOT considered for equality, is purely for
            # description
            if (wv1.i == wv2.i and
                wv1.w_static_type is wv2.w_static_type):
                return B.w_True
            else:
                return B.w_False

        if w_ltype is w_rtype:
            return W_OpImpl.simple(vm.wrap_func(eq))
        else:
            return W_OpImpl.NULL



@spytype('OpImpl')
class W_OpImpl(W_Object):
    NULL: ClassVar['W_OpImpl']
    _w_func: Optional[W_Func]
    _args_wv: Optional[list[W_Value]]

    def __init__(self, *args) -> None:
        raise NotImplementedError('Please use W_OpImpl.simple()')

    @classmethod
    def simple(cls, w_func: W_Func) -> 'W_OpImpl':
        w_opimpl = cls.__new__(cls)
        w_opimpl._w_func = w_func
        w_opimpl._args_wv = None
        return w_opimpl

    @classmethod
    def with_values(cls, w_func: W_Func, args_wv: list[W_Value]) -> 'W_OpImpl':
        w_opimpl = cls.__new__(cls)
        w_opimpl._w_func = w_func
        w_opimpl._args_wv = args_wv
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

    def call(self, vm: 'SPyVM', args_w: list[W_Object]) -> W_Object:
        if self._args_wv is not None:
            args_w = [args_w[wv.i] for wv in self._args_wv]
        return vm.call(self._w_func, args_w)

W_OpImpl.NULL = W_OpImpl.simple(None)
