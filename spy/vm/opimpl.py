from typing import (Annotated, Optional, ClassVar, no_type_check, TypeVar, Any,
                    TYPE_CHECKING)
from spy import ast
from spy.fqn import QN
from spy.location import Loc
from spy.vm.object import Member, W_Type, W_Object, spytype, W_Bool
from spy.vm.function import W_Func, W_FuncType
from spy.vm.sig import spy_builtin

if TYPE_CHECKING:
    from spy.vm.typeconverter import TypeConverter

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

    @classmethod
    def from_w_obj(cls, vm: 'SPyVM', w_obj: W_Object,
                   prefix: str, i: int) -> 'W_Value':
        w_type = vm.dynamic_type(w_obj)
        return W_Value(prefix, i, w_type, None, w_blueval=w_obj)

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
    def op_EQ(vm: 'SPyVM', wv_l: 'W_Value', wv_r: 'W_Value') -> 'W_OpImpl':
        w_ltype = wv_l.w_static_type
        w_rtype = wv_r.w_static_type
        assert w_ltype.pyclass is W_Value

        if w_ltype is w_rtype:
            return W_OpImpl.simple(vm.wrap_func(value_eq))
        else:
            return W_OpImpl.NULL


@no_type_check
@spy_builtin(QN('operator::value_eq'))
def value_eq(vm: 'SPyVM', wv1: W_Value, wv2: W_Value) -> W_Bool:
    from spy.vm.b import B
    # note that the prefix is NOT considered for equality, is purely for
    # description
    if wv1.i != wv2.i:
        return B.w_False
    if wv1.w_static_type is not wv2.w_static_type:
        return B.w_False
    if (wv1.is_blue() and
        wv2.is_blue() and
        vm.is_False(vm.eq(wv1._w_blueval, wv2._w_blueval))):
        return B.w_False
    return B.w_True




@spytype('OpImpl')
class W_OpImpl(W_Object):
    NULL: ClassVar['W_OpImpl']
    _w_func: Optional[W_Func]
    _args_wv: Optional[list[W_Value]]
    _converters: Optional[list[Optional['TypeConverter']]]

    def __init__(self, *args) -> None:
        raise NotImplementedError('Please use W_OpImpl.simple()')

    @classmethod
    def simple(cls, w_func: W_Func) -> 'W_OpImpl':
        w_opimpl = cls.__new__(cls)
        w_opimpl._w_func = w_func
        w_opimpl._args_wv = None
        w_opimpl._converters = None
        return w_opimpl

    @classmethod
    def with_values(cls, w_func: W_Func, args_wv: list[W_Value]) -> 'W_OpImpl':
        w_opimpl = cls.__new__(cls)
        w_opimpl._w_func = w_func
        w_opimpl._args_wv = args_wv
        w_opimpl._converters = [None] * len(args_wv)
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
    def w_functype(self) -> W_FuncType:
        return self._w_func.w_functype

    @property
    def w_restype(self) -> W_Type:
        return self._w_func.w_functype.w_restype

    def set_args_wv(self, args_wv):
        assert self._args_wv is None
        assert self._converters is None
        self._args_wv = args_wv[:]
        self._converters = [None] * len(args_wv)

    def reorder(self, args: list[T]) -> list[T]:
        """
        If we have a complex W_OpImpl, we want to reorder the given args
        depending on the order of _args_wv
        """
        if self._args_wv is None:
            return args
        else:
            return [args[wv.i] for wv in self._args_wv]

    def call(self, vm: 'SPyVM', orig_args_w: list[W_Object]) -> W_Object:
        real_args_w = []
        for wv_arg, conv in zip(self._args_wv, self._converters):
            w_arg = orig_args_w[wv_arg.i]
            if conv is not None:
                w_arg = conv.convert(vm, w_arg)
            real_args_w.append(w_arg)
        return vm.call(self._w_func, real_args_w)

    def redshift_args(self, vm: 'SPyVM',
                      orig_args: list[ast.Expr]) -> list[ast.Expr]:
        real_args = []
        for wv_arg, conv in zip(self._args_wv, self._converters):
            arg = orig_args[wv_arg.i]
            if conv is not None:
                arg = conv.redshift(vm, arg)
            real_args.append(arg)
        return real_args


W_OpImpl.NULL = W_OpImpl.simple(None)
