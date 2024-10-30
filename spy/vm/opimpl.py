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
from spy.fqn import QN
from spy.location import Loc
from spy.irgen.symtable import Symbol
from spy.vm.object import Member, W_Type, W_Object, spytype, W_Bool
from spy.vm.function import W_Func, W_FuncType, W_DirectCall
from spy.vm.sig import spy_builtin

if TYPE_CHECKING:
    from spy.vm.typeconverter import TypeConverter

T = TypeVar('T')

@spytype('OpArg')
class W_OpArg(W_Object):
    """
    OpArgs represents the operands passed to OPERATORs.

    All values have a w_static_type; blue values have also a w_blueval.

    The naming convention is wop_one and manyvalues_wop.
    """
    prefix: str
    i: int
    w_static_type: Annotated[W_Type, Member('static_type')]
    loc: Optional[Loc]
    sym: Optional[Symbol]
    _w_blueval: Optional[W_Object]

    def __init__(self,
                 prefix: str,
                 i: int,
                 w_static_type: W_Type,
                 loc: Optional[Loc],
                 *,
                 sym: Optional[Symbol] = None,
                 w_blueval: Optional[W_Object] = None,
                 ) -> None:
        self.prefix = prefix
        self.i = i
        self.w_static_type = w_static_type
        self.loc = loc
        self.sym = sym
        self._w_blueval = w_blueval

    @classmethod
    def from_w_obj(cls, vm: 'SPyVM', w_obj: W_Object,
                   prefix: str, i: int) -> 'W_OpArg':
        w_type = vm.dynamic_type(w_obj)
        return W_OpArg(prefix, i, w_type, None, w_blueval=w_obj)

    @property
    def name(self):
        return f'{self.prefix}{self.i}'

    def __repr__(self):
        if self.is_blue():
            extra = f' = {self._w_blueval}'
        else:
            extra = ''
        return f'<W_OpArg {self.name}: {self.w_static_type.name}{extra}>'

    def is_blue(self):
        return self._w_blueval is not None

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
    def op_EQ(vm: 'SPyVM', wop_l: 'W_OpArg', wop_r: 'W_OpArg') -> 'W_OpImpl':
        w_ltype = wop_l.w_static_type
        w_rtype = wop_r.w_static_type
        assert w_ltype.pyclass is W_OpArg

        if w_ltype is w_rtype:
            return W_OpImpl(vm.wrap_func(value_eq))
        else:
            return W_OpImpl.NULL


@no_type_check
@spy_builtin(QN('operator::value_eq'))
def value_eq(vm: 'SPyVM', wop1: W_OpArg, wop2: W_OpArg) -> W_Bool:
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




@spytype('OpImpl')
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
            argnames = [wop.name for wop in self._args_wop]
            argnames = ', '.join(argnames)
            return f"<spy OpImpl {qn}({argnames})>"

    def is_null(self) -> bool:
        return self._w_func is None

    def is_simple(self) -> bool:
        return self._args_wop is None

    def is_direct_call(self):
    """
        This is a hack. See W_Func.op_CALL and ASTFrame.eval_expr_Call.
        """
        return isinstance(self._w_func, W_DirectCall)

    def is_valid(self):
        return not self.is_null() and self._typechecked

    @property
    def w_functype(self) -> W_FuncType:
        return self._w_func.w_functype

    @property
    def w_restype(self) -> W_Type:
        return self._w_func.w_functype.w_restype

    def set_args_wop(self, args_wop):
        assert self._args_wop is None
        assert self._converters is None
        self._args_wop = args_wop[:]
        self._converters = [None] * len(args_wop)

    def call(self, vm: 'SPyVM', orig_args_w: list[W_Object]) -> W_Object:
        assert self.is_valid()
        real_args_w = []
        for wop_arg, conv in zip(self._args_wop, self._converters):
            # XXX we definitely need a better way to handle "constant" W_OpArgs
            if wop_arg.i == 999:
                assert wop_arg.w_blueval is not None
                w_arg = wop_arg.w_blueval
            else:
                w_arg = orig_args_w[wop_arg.i]

            if conv is not None:
                w_arg = conv.convert(vm, w_arg)
            real_args_w.append(w_arg)
        #
        if self.is_direct_call():
            w_func = orig_args_w[0]
            return vm.call(w_func, real_args_w)
        else:
            return vm.call(self._w_func, real_args_w)

    def redshift_args(self, vm: 'SPyVM',
                      orig_args: list[ast.Expr]) -> list[ast.Expr]:
        from spy.doppler import make_const
        assert self.is_valid()
        real_args = []
        for wop_arg, conv in zip(self._args_wop, self._converters):
            # XXX we definitely need a better way to handle "constant" W_OpArg
            if wop_arg.i == 999:
                assert wop_arg.w_blueval is not None
                w_arg = wop_arg.w_blueval
                arg = make_const(vm, wop_arg.loc, w_arg)
            else:
                arg = orig_args[wop_arg.i]

            if conv is not None:
                arg = conv.redshift(vm, arg)
            real_args.append(arg)
        return real_args


W_OpImpl.NULL = W_OpImpl(None)
