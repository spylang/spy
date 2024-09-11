from typing import Annotated, Optional, ClassVar, no_type_check, TypeVar, Any
from spy import ast
from spy.fqn import QN
from spy.location import Loc
from spy.vm.object import Member, W_Type, W_Object, spytype, W_Bool
from spy.vm.function import W_Func
from spy.vm.sig import spy_builtin

T = TypeVar('T')

@spytype('Value')
class W_Value(W_Object):
    """
    A Value represent an operand of an OPERATOR.

    All values have a w_static_type; blue values have also a w_blueval.

    The naming convention is wv_one and manyvalues_wv.
    """
    prefix: str
    i: int
    w_static_type: Annotated[W_Type, Member('static_type')]
    loc: Optional[Loc]
    _w_blueval: Optional[W_Object]

    def __init__(self,
                 prefix: str,
                 i: int,
                 w_static_type: W_Type,
                 loc: Optional[Loc],
                 *,
                 w_blueval: Optional[W_Object] = None,
                 ) -> None:
        self.prefix = prefix
        self.i = i
        self.w_static_type = w_static_type
        self.loc = loc
        self._w_blueval = w_blueval

    @property
    def name(self):
        return f'{self.prefix}{self.i}'

    def __repr__(self):
        if self.is_blue():
            extra = f' = {self._w_blueval}'
        else:
            extra = ''
        return f'<W_Value {self.name}: {self.w_static_type.name}{extra}>'

    def is_blue(self):
        return self._w_blueval is not None

    @property
    def w_blueval(self) -> W_Object:
        assert self._w_blueval is not None
        return self._w_blueval

    def blue_ensure(self, vm: 'SPyVM', w_expected_type: W_Type) -> W_Object:
        """
        Ensure that the W_Value is blue and of the expected type.
        Raise SPyTypeError if not.
        """
        from spy.vm.typechecker import convert_type_maybe
        if not self.is_blue():
            raise SPyTypeError.simple(
                'expected blue argument',
                'this is red',
                self.loc)
        err = convert_type_maybe(vm, self, w_expected_type)
        if err:
            raise err
        return self._w_blueval

    def blue_unwrap(self, vm: 'SPyVM', w_expected_type: W_Type) -> Any:
        """
        Like ensure_blue, but also unwrap.
        """
        w_obj = self.blue_ensure(vm, w_expected_type)
        return vm.unwrap(w_obj)

    def blue_unwrap_str(self, vm: 'SPyVM') -> str:
        from spy.vm.b import B
        self.blue_ensure(vm, B.w_str)
        return vm.unwrap_str(self._w_blueval)

    @staticmethod
    def op_EQ(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> 'W_OpImpl':
        from spy.vm.b import B
        assert w_ltype.pyclass is W_Value

        @no_type_check
        @spy_builtin(QN('operator::value_eq'))
        def eq(vm: 'SPyVM', wv1: W_Value, wv2: W_Value) -> W_Bool:
            # note that the prefix is NOT considered for equality, is purely for
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
        elif self._args_wv is None:
            qn = self._w_func.qn
            return f"<spy OpImpl {qn}>"
        else:
            qn = self._w_func.qn
            argnames = [wv.name for wv in self._args_wv]
            argnames = ', '.join(argnames)
            return f"<spy OpImpl {qn}({argnames})>"

    def is_null(self) -> bool:
        return self._w_func is None

    def is_simple(self) -> bool:
        return self._args_wv is None

    @property
    def w_func(self) -> W_Func:
        assert self._w_func is not None
        return self._w_func

    @property
    def w_restype(self) -> W_Type:
        return self.w_func.w_functype.w_restype

    def reorder(self, args: list[T]) -> list[T]:
        """
        If we have a complex W_OpImpl, we want to reorder the given args
        depending on the order of _args_wv
        """
        if self._args_wv is None:
            return args
        else:
            return [args[wv.i] for wv in self._args_wv]


W_OpImpl.NULL = W_OpImpl.simple(None)
