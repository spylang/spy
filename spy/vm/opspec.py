"""
OpSpec and OpImpl is the central concept to understand of SPy operators work.

Conceptually, the following SPy code:
   c = a + b

is roughly equivalent to:
   arg_a = OpArg('a', STATIC_TYPE(a))
   arg_b = OpArg('b', STATIC_TYPE(b))
   opimpl = operator.ADD(arg_a, arg_b)
   c = opimpl(a, b)

I.e., the execution of an operator happens in three-steps:
  1. We call the OPERATOR to determine the OpSpec
  2. The VM convert the OpSpec into an executable OpImpl
  3. We call the OpImpl to determine the final results.

Point (2) is where typechecking happens and can fail.

Note that OPERATORTs don't receive the actual values of operands. Instead,
they receive OpArgs, which represents "abstract values", of which we know only
the static type.

Then, the OpImpl receives the actual values and compute the result.

This scheme is designed in such a way that the call to OPERATOR() is always
blue and can be optimized away during redshifting.
"""

from typing import (Annotated, Optional, ClassVar, no_type_check, Any,
                    TYPE_CHECKING)
from spy.location import Loc
from spy.analyze.symtable import Symbol, Color
from spy.errors import SPyError
from spy.vm.b import OPERATOR, B
from spy.vm.object import W_Type, W_Object
from spy.vm.member import Member
from spy.vm.function import W_Func, W_FuncType
from spy.vm.builtin import (builtin_func, builtin_method, builtin_property,
                            builtin_class_attr)
from spy.vm.primitive import W_Bool
from spy.vm.property import W_Property

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM
    from spy.vm.primitive import W_Dynamic
    from spy.vm.str import W_Str


@OPERATOR.builtin_type('OpArg', lazy_definition=True)
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
    dispatch to the proper OpSpec.

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

    @builtin_method('__new__')
    @staticmethod
    def w_new(
            vm: 'SPyVM',
            w_color: W_Object,
            w_static_type: W_Type,
            w_val: W_Object
    ) -> 'W_OpArg':
        """
        Create a new OpArg from SPy code:
        - color: 'red' or 'blue'
        - static_type: the static type of the argument
        - val: the value (optional for red OpArg, required for blue)
        """
        # Check that w_color is a string
        w_T = vm.dynamic_type(w_color)
        if w_T is not B.w_str:
            raise SPyError(
                'W_TypeError',
                f"OpArg color must be a string, got {w_T.fqn.human_name}",
            )

        color: Color = vm.unwrap_str(w_color)  # type: ignore
        if color not in ('red', 'blue'):
            raise SPyError(
                'W_TypeError',
                f"OpArg color must be 'red' or 'blue', got '{color}'",
            )

        # Convert B.w_None to Python None
        if w_val is B.w_None:
            w_val2 = None
        else:
            w_val2 = w_val

        if color == 'blue' and w_val is None:
            raise SPyError("Blue OpArg requires a value", etype='W_TypeError')

        loc = Loc.here(-2)  # approximate source location
        return W_OpArg(vm, color, w_static_type, w_val2, loc)

    @classmethod
    def from_w_obj(cls, vm: 'SPyVM', w_obj: W_Object) -> 'W_OpArg':
        w_T = vm.dynamic_type(w_obj)
        return W_OpArg(vm, 'blue', w_T, w_obj, Loc.here(-2))

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
        Raise SPyError(W_TypeError) if not.
        """
        from spy.vm.modules.operator.convop import CONVERT_maybe
        if self.color != 'blue':
            raise SPyError.simple(
                'W_TypeError',
                'expected blue argument',
                'this is red',
                self.loc,
            )

        # check that the blueval has the expected type. If not, we should
        # probably raise a better error, but for now we just fail with
        # AssertionError.
        w_func = CONVERT_maybe(vm, w_expected_type, self)
        assert w_func is None
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

    @builtin_method('__convert_from__', color='blue', kind='metafunc')
    @staticmethod
    def w_CONVERT_FROM(vm: 'SPyVM', wop_T: 'W_OpArg',
                       wop_x: 'W_OpArg') -> 'W_OpSpec':
        w_T = wop_T.w_blueval
        assert isinstance(w_T, W_Type)
        if vm.issubclass(w_T, B.w_type):
            @builtin_func(W_OpArg._w.fqn, 'from_type')
            def w_from_type(vm: 'SPyVM', w_type: W_Type) -> W_OpArg:
                return W_OpArg(
                    vm,
                    color='red',
                    w_static_type=w_type,
                    w_val=None,
                    loc=Loc.here()  # w_from_type
                )
            return W_OpSpec(w_from_type)
        return W_OpSpec.NULL

    @builtin_method('__eq__', color='blue', kind='metafunc')
    @staticmethod
    def w_EQ(vm: 'SPyVM', wop_l: 'W_OpArg', wop_r: 'W_OpArg') -> 'W_OpSpec':
        w_ltype = wop_l.w_static_type
        w_rtype = wop_r.w_static_type
        assert w_ltype.pyclass is W_OpArg

        if w_ltype is w_rtype:
            return W_OpSpec(w_oparg_eq)
        else:
            return W_OpSpec.NULL

    @builtin_property('color')
    @staticmethod
    def w_get_color(vm: 'SPyVM', w_self: 'W_OpArg') -> 'W_Str':
        """
        Applevel property to get the color. We cannot use a simple Member
        because the applevel type (W_Str) doesn't match the interp-level type
        (Color).
        """
        return vm.wrap(w_self.color)

    @builtin_property('blueval')
    @staticmethod
    def w_get_blueval(vm: 'SPyVM', w_self: 'W_OpArg') -> 'W_Dynamic':
        """
        Applevel property to get the blueval. We cannot use a simple
        Member because we want to do an extra check and raise W_ValueError if
        the color is not blue.
        """
        if w_self.color != 'blue':
            raise SPyError('W_ValueError', 'oparg is not blue')
        return w_self.w_blueval


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


@OPERATOR.builtin_type('OpSpec', lazy_definition=True)
class W_OpSpec(W_Object):
    NULL: ClassVar['W_OpSpec']

    # this is a mess: depending on the presence of some of these attributes
    # the OpSpec can be "NULL", "simple", "complex" and "const". Ideally, we
    # we would like a proper sum type with disjoint attributes, but
    # Python/mypy support for it is very limited and makes things more
    # complicated.
    #
    # The invariants are
    #    - at most one of _w_func and _w_const should be non None
    #    - _args_wop makes sense only if _w_func is non None
    #    - is_direct_call makes sense only if _w_const is None
    _w_func: Optional[W_Func]
    _args_wop: Optional[list[W_OpArg]]
    _w_const: Optional[W_Object]
    is_direct_call: bool

    # default constructor, for "NULL", "simple" and "complex" cases
    def __init__(self,
                 w_func: Optional[W_Func],
                 args_wop: Optional[list[W_OpArg]] = None,
                 *,
                 is_direct_call: bool = False,
                ) -> None:
        self._w_func = w_func
        self._args_wop = args_wop
        self.is_direct_call = is_direct_call
        self._w_const = None

    # constructor for the "const" case
    @staticmethod
    def const(w_obj: W_Object) -> 'W_OpSpec':
        w_opspec = W_OpSpec(None, None)
        w_opspec._w_const = w_obj
        return w_opspec

    def __repr__(self) -> str:
        if self._w_func is None:
            return f"<spy OpSpec NULL>"
        elif self._args_wop is None:
            fqn = self._w_func.fqn
            return f"<spy OpSpec {fqn}>"
        elif self._w_const is not None:
            return f"<spy OpSpec const {self._w_const}>"
        else:
            fqn = self._w_func.fqn
            return f"<spy OpSpec {fqn}(...)>"

    def is_null(self) -> bool:
        return self._w_func is None and self._w_const is None

    def is_simple(self) -> bool:
        return self._w_func is not None and self._args_wop is None

    def is_complex(self) -> bool:
        return self._w_func is not None and self._args_wop is not None

    def is_const(self) -> bool:
        return self._w_const is not None

    @property
    def w_functype(self) -> W_FuncType:
        assert self._w_func is not None
        return self._w_func.w_functype

    # ======== app-level interface ========

    @builtin_method('__new__', color='blue', kind='metafunc')
    @staticmethod
    def w_NEW(vm: 'SPyVM', wop_cls: W_OpArg, *args_wop: W_OpArg) -> 'W_OpSpec':
        """
        Operator for creating OpSpec instances with different argument counts.
        - OpSpec(func) -> Simple OpSpec
        - OpSpec(func, args) -> OpSpec with pre-filled arguments
        """
        from spy.vm.function import W_Func
        from spy.vm.list import W_OpArgList

        w_T = wop_cls.w_blueval
        assert isinstance(w_T, W_Type)

        if len(args_wop) == 1:
            # Simple case: OpSpec(func)
            @builtin_func(w_T.fqn, 'new1')
            def w_new1(vm: 'SPyVM', w_cls: W_Type, w_func: W_Func) -> W_OpSpec:
                return W_OpSpec(w_func)
            return W_OpSpec(w_new1)

        elif len(args_wop) == 2:
            # OpSpec(func, args) case
            @builtin_func(w_T.fqn, 'new2')
            def w_new2(vm: 'SPyVM', w_cls: W_Type,
                       w_func: W_Func, w_args: W_OpArgList) -> W_OpSpec:
                # Convert from applevel w_args into interp-level args_w
                args_w = w_args.items_w[:]
                return W_OpSpec(w_func, args_w)
            return W_OpSpec(w_new2)
        else:
            return W_OpSpec.NULL

# make W_OpSpec.NULL available also at applevel, thanks to builtin_class_attr
W_OpSpec.NULL = builtin_class_attr('NULL', W_OpSpec(None))  # type: ignore
