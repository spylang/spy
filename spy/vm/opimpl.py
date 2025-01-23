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
from spy.irgen.symtable import Symbol, Color
from spy.errors import SPyTypeError
from spy.vm.b import OPERATOR, B
from spy.vm.object import Member, W_Type, W_Object, builtin_method
from spy.vm.function import W_Func, W_FuncType
from spy.vm.builtin import builtin_func, builtin_type
from spy.vm.primitive import W_Bool

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

T = TypeVar('T')

@OPERATOR.builtin_type('OpArg')
class W_OpArg(W_Object):
    """
    A value which carries some extra information.
    This is a central part of how SPy works.

    In order to preserve the same semantics between interp and compile,
    operation dispatch must be done on STATIC types. The same object can have
    different static types, and thus respond to different operations. For
    example:
        x: MyClass = ...
        y: object = x

    x and y are identical, but have different static types.

    The main job of OpArgs is to keep track of the color and the static type
    of objects inside the ASTFrame.  As the name suggests, they are then
    passed as arguments to OPERATORs, which can then use the static type to
    dispatch to the proper OpImpl.

    Moreover, they carry around extra information which are used to produce
    better error messages, when needed:
      - loc: the source code location where this object comes from
      - sym: the symbol associated with this objects (if any)

    In interpreter mode, OpArgs represent concrete values, so they carry an
    actualy object + its static type.

    During redshifting, red OpArgs are abstract: they carry around only the
    static types.

    Blue OpArg always have an associated value.
    """
    color: Color
    w_static_type: Annotated[W_Type, Member('static_type')]
    loc: Loc
    _w_val: Optional[W_Object]
    sym: Optional[Symbol]

    def __init__(self,
                 vm: 'SPyVM',
                 color: Color,
                 w_static_type: W_Type,
                 w_val: Optional[W_Object],
                 loc: Loc,
                 *,
                 sym: Optional[Symbol] = None,
                 ) -> None:
        if color == 'blue':
            assert w_val is not None
            if w_static_type is B.w_dynamic:
                # "dynamic blue" doesn't make sense: if it's blue, we
                # precisely know its type, and we can eagerly evaluate it.
                # See test_basic::test_eager_blue_eval
                w_static_type = vm.dynamic_type(w_val)
        self.color = color
        self.w_static_type = w_static_type
        self._w_val = w_val
        self.loc = loc
        self.sym = sym

    @classmethod
    def from_w_obj(cls, vm: 'SPyVM', w_obj: W_Object) -> 'W_OpArg':
        w_type = vm.dynamic_type(w_obj)
        return W_OpArg(vm, 'blue', w_type, w_obj, Loc.here(-2))

    def __repr__(self) -> str:
        if self.is_blue():
            extra = f' = {self.w_val}'
        else:
            extra = ''
        t = self.w_static_type.fqn.human_name
        return f'<W_OpArg {self.color} {t}{extra}>'

    def is_blue(self) -> bool:
        return self.color == 'blue'

    def as_red(self, vm: 'SPyVM') -> 'W_OpArg':
        if self.color == 'red':
            return self
        return W_OpArg(vm, 'red', self.w_static_type, self._w_val, self.loc,
                       sym=self.sym)

    @property
    def w_val(self) -> W_Object:
        assert self._w_val is not None, 'cannot read w_val from abstract OpArg'
        return self._w_val

    @property
    def w_blueval(self) -> W_Object:
        assert self.color == 'blue'
        assert self._w_val is not None
        return self._w_val

    def blue_ensure(self, vm: 'SPyVM', w_expected_type: W_Type) -> W_Object:
        """
        Ensure that the W_OpArg is blue and of the expected type.
        Raise SPyTypeError if not.
        """
        from spy.vm.modules.operator.convop import CONVERT_maybe
        if self.color != 'blue':
            raise SPyTypeError.simple(
                'expected blue argument',
                'this is red',
                self.loc)

        # check that the blueval has the expected type. If not, we should
        # probably raise a better error, but for now we just fail with
        # AssertionError.
        w_opimpl = CONVERT_maybe(vm, w_expected_type, self)
        assert w_opimpl is None
        assert self.w_val is not None
        return self.w_val

    def blue_unwrap(self, vm: 'SPyVM', w_expected_type: W_Type) -> Any:
        """
        Like ensure_blue, but also unwrap.
        """
        w_obj = self.blue_ensure(vm, w_expected_type)
        return vm.unwrap(w_obj)

    def blue_unwrap_str(self, vm: 'SPyVM') -> str:
        from spy.vm.b import B
        self.blue_ensure(vm, B.w_str)
        assert self.w_val is not None
        return vm.unwrap_str(self.w_val)

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
    """
    Two red opargs are equal if they have the same static types.
    Two blue opargs are equal if they also have the same values.
    """
    from spy.vm.b import B
    # note that the prefix is NOT considered for equality, is purely for
    # description
    if wop1.w_static_type is not wop2.w_static_type:
        return B.w_False
    # we need to think what to do in this case
    ## if wop1.is_blue() != wop2.is_blue():
    ##     import pdb;pdb.set_trace()
    if (wop1.is_blue() and
        wop2.is_blue() and
        vm.is_True(vm.universal_ne(wop1.w_val, wop2.w_val))):
        return B.w_False
    return B.w_True




@OPERATOR.builtin_type('OpImpl')
class W_OpImpl(W_Object):
    __spy_lazy_init__ = True

    NULL: ClassVar['W_OpImpl']
    _w_func: Optional[W_Func]
    _args_wop: Optional[list[W_OpArg]]
    is_direct_call: bool

    def __init__(self,
                 w_func: W_Func,
                 args_wop: Optional[list[W_OpArg]] = None,
                 *,
                 is_direct_call: bool = False,
                ) -> None:
        self._w_func = w_func
        self._args_wop = args_wop
        self.is_direct_call = is_direct_call

    def __repr__(self) -> str:
        if self._w_func is None:
            return f"<spy OpImpl NULL>"
        elif self._args_wop is None:
            fqn = self._w_func.fqn
            return f"<spy OpImpl {fqn}>"
        else:
            fqn = self._w_func.fqn
            return f"<spy OpImpl {fqn}(...)>"

    def is_null(self) -> bool:
        return self._w_func is None

    def is_simple(self) -> bool:
        return self._args_wop is None

    @property
    def w_functype(self) -> W_FuncType:
        assert self._w_func is not None
        return self._w_func.w_functype

    # ======== app-level interface ========

    @builtin_method('__new__')
    @staticmethod
    def w_spy_new(vm: 'SPyVM', w_cls: W_Type, w_func: W_Func) -> 'W_OpImpl':
        return W_OpImpl(w_func)


W_OpImpl.NULL = W_OpImpl(None)  # type: ignore
