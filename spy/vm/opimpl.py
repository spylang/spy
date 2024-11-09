"""
OpImpl is the central concept to understand of SPy operators work.

Conceptually, the following SPy code:
   c = a + b

is roughly equivalent to:
   arg_a = OpArg('a', STATIC_TYPE(a))
   arg_b = OpArg('b', STATIC_TYPE(b))
   opimpl = operator.ADD(arg_a, arg_b)
   c = opimpl(a, b)

I.e., the execution of an operator happens in two-steps:
  1. first, we call the OPERATOR to determine the opimpl
  2. then, we call the opimpl to determine the final results.

Note that OPERATORTs don't receive the actual values of operands. Instead,
they receive OpArgs, which represents "abstract values", of which we know only
the static type.

Then, the OpImpl receives the actual values and compute the result.

This scheme is designed in such a way that the call to OPERATOR() is always
blue and can be optimized away during redshifting.
"""

from typing import (Annotated, Optional, ClassVar, no_type_check, TypeVar, Any,
                    TYPE_CHECKING)
from spy import ast
from spy.location import Loc
from spy.irgen.symtable import Symbol
from spy.errors import SPyTypeError
from spy.vm.object import Member, W_Type, W_Object
from spy.vm.function import W_Func, W_FuncType, W_DirectCall
from spy.vm.builtin import builtin_func, builtin_type
from spy.vm.primitive import W_Bool

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM
    from spy.vm.typeconverter import TypeConverter

T = TypeVar('T')

@builtin_type('operator', 'OpArg')
class W_OpArg(W_Object):
    """
    Class which represents the operands passed to OPERATORs.

    There are two kinds of operands:

      - "proper" OpArgs, which refers to a value which will be known later at
        runtime.

      - OpConsts, which can be synthetized inside OPERATORs, in case they want
        to pass a const to an opimpl.

    In some cases, the *actual value* of an OpArg might be known at
    compile time, if it comes from a blue expression: in this case, we also
    set w_blueval.

    The naming convention is wop_one and manyvalues_wop.

    Internally, an OpConst is represented as an OpArg whose .i is None.
    """
    prefix: str
    i: Optional[int]
    w_static_type: Annotated[W_Type, Member('static_type')]
    loc: Loc
    sym: Optional[Symbol]
    _w_blueval: Optional[W_Object]

    def __init__(self,
                 prefix: str,
                 i: Optional[int],
                 w_static_type: W_Type,
                 loc: Loc,
                 *,
                 sym: Optional[Symbol] = None,
                 w_blueval: Optional[W_Object] = None,
                 ) -> None:
        if i is None:
            assert w_blueval is not None
        self.prefix = prefix
        self.i = i
        self.w_static_type = w_static_type
        self.loc = loc
        self.sym = sym
        self._w_blueval = w_blueval

    @classmethod
    def const(cls, vm: 'SPyVM', w_obj: W_Object, prefix: str) -> 'W_OpArg':
        w_type = vm.dynamic_type(w_obj)
        return cls(prefix, None, w_type, Loc.here(-2), w_blueval=w_obj)

    @classmethod
    def from_w_obj(cls, vm: 'SPyVM', w_obj: W_Object,
                   prefix: str, i: int) -> 'W_OpArg':
        w_type = vm.dynamic_type(w_obj)
        return W_OpArg(prefix, i, w_type, Loc.here(-2), w_blueval=w_obj)

    @property
    def name(self) -> str:
        return f'{self.prefix}{self.i}'

    def __repr__(self) -> str:
        if self.is_blue():
            extra = f' = {self._w_blueval}'
        else:
            extra = ''
        if self.is_const():
            extra += ' const'
        return f'<W_OpArg {self.name}: {self.w_static_type.qn}{extra}>'

    def is_blue(self) -> bool:
        return self._w_blueval is not None

    def is_const(self) -> bool:
        return self.i is None

    @property
    def w_blueval(self) -> W_Object:
        assert self._w_blueval is not None
        return self._w_blueval

    def blue_ensure(self, vm: 'SPyVM', w_expected_type: W_Type) -> W_Object:
        """
        Ensure that the W_OpArg is blue and of the expected type.
        Raise SPyTypeError if not.
        """
        from spy.vm.typechecker import convert_type_maybe
        if self._w_blueval is None:
            raise SPyTypeError.simple(
                'expected blue argument',
                'this is red',
                self.loc)
        err = convert_type_maybe(vm, self, w_expected_type)
        if err:
            assert isinstance(err, BaseException)
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
        assert self._w_blueval is not None
        return vm.unwrap_str(self._w_blueval)

    @staticmethod
    def op_EQ(vm: 'SPyVM', wop_l: 'W_OpArg', wop_r: 'W_OpArg') -> 'W_OpImpl':
        w_ltype = wop_l.w_static_type
        w_rtype = wop_r.w_static_type
        assert w_ltype.pyclass is W_OpArg

        if w_ltype is w_rtype:
            return W_OpImpl(w_oparg_eq)
        else:
            return W_OpImpl.NULL


@no_type_check
@builtin_func('operator')
def w_oparg_eq(vm: 'SPyVM', wop1: W_OpArg, wop2: W_OpArg) -> W_Bool:
    from spy.vm.b import B
    # note that the prefix is NOT considered for equality, is purely for
    # description
    if wop1.i != wop2.i:
        return B.w_False
    if wop1.w_static_type is not wop2.w_static_type:
        return B.w_False
    if (wop1.is_blue() and
        wop2.is_blue() and
        vm.is_False(vm.eq(wop1._w_blueval, wop2._w_blueval))):
        return B.w_False
    return B.w_True




@builtin_type('operator', 'OpImpl')
class W_OpImpl(W_Object):
    NULL: ClassVar['W_OpImpl']
    _w_func: Optional[W_Func]
    _args_wop: Optional[list[W_OpArg]]
    _converters: Optional[list[Optional['TypeConverter']]]

    def __init__(self,
                 w_func: W_Func,
                args_wop: Optional[list[W_OpArg]] = None
                ) -> None:
        self._w_func = w_func
        self._typechecked = False
        if args_wop is None:
            self._args_wop = None
            self._converters = None
        else:
            self._args_wop = args_wop
            self._converters = [None] * len(args_wop)

    def __repr__(self) -> str:
        if self._w_func is None:
            return f"<spy OpImpl NULL>"
        elif self._args_wop is None:
            qn = self._w_func.qn
            return f"<spy OpImpl {qn}>"
        else:
            qn = self._w_func.qn
            argnames = ', '.join([wop.name for wop in self._args_wop])
            return f"<spy OpImpl {qn}({argnames})>"

    def is_null(self) -> bool:
        return self._w_func is None

    def is_simple(self) -> bool:
        return self._args_wop is None

    def is_direct_call(self) -> bool:
        """
        This is a hack. See W_Func.op_CALL and ASTFrame.eval_expr_Call.
        """
        return isinstance(self._w_func, W_DirectCall)

    def is_valid(self) -> bool:
        return not self.is_null() and self._typechecked

    @property
    def w_functype(self) -> W_FuncType:
        assert self._w_func is not None
        return self._w_func.w_functype

    @property
    def w_restype(self) -> W_Type:
        assert self._w_func is not None
        return self._w_func.w_functype.w_restype

    def set_args_wop(self, args_wop: list[W_OpArg]) -> None:
        assert self._args_wop is None
        assert self._converters is None
        self._args_wop = args_wop[:]
        self._converters = [None] * len(args_wop)

    def call(self, vm: 'SPyVM', orig_args_w: list[W_Object]) -> W_Object:
        assert self.is_valid()
        assert self._args_wop is not None
        assert self._converters is not None
        real_args_w = []
        for wop_arg, conv in zip(self._args_wop, self._converters):
            if wop_arg.is_const():
                w_arg = wop_arg.w_blueval
            else:
                assert wop_arg.i is not None
                w_arg = orig_args_w[wop_arg.i]

            if conv is not None:
                w_arg = conv.convert(vm, w_arg)
            real_args_w.append(w_arg)
        #
        if self.is_direct_call():
            w_func = orig_args_w[0]
            assert isinstance(w_func, W_Func)
            return vm.call(w_func, real_args_w)
        else:
            assert self._w_func is not None
            return vm.call(self._w_func, real_args_w)

    def redshift_args(self, vm: 'SPyVM',
                      orig_args: list[ast.Expr]) -> list[ast.Expr]:
        from spy.doppler import make_const
        assert self.is_valid()
        assert self._args_wop is not None
        assert self._converters is not None
        real_args = []
        for wop_arg, conv in zip(self._args_wop, self._converters):
            if wop_arg.is_const():
                w_arg = wop_arg.w_blueval
                arg = make_const(vm, wop_arg.loc, w_arg)
            else:
                assert wop_arg.i is not None
                arg = orig_args[wop_arg.i]

            if conv is not None:
                arg = conv.redshift(vm, arg)
            real_args.append(arg)
        return real_args


W_OpImpl.NULL = W_OpImpl(None)  # type: ignore
