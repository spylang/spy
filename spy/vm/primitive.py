from typing import Annotated, ClassVar, TYPE_CHECKING
import fixedint
from spy.fqn import FQN
from spy.vm.object import W_Object, W_Type
from spy.vm.b import B

# fixedint/__init__.pyi overrides FixedInt and mypy thinks it's a
# function. Let's convince it back that it's a type
if TYPE_CHECKING:
    from fixedint import _FixedInt as FixedInt
else:
    from fixedint import FixedInt

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

@B.builtin_type('void')
class W_Void(W_Object):
    """
    Equivalent of Python's NoneType.

    This is a singleton: there should be only one instance of this class,
    which is w_None.
    """
    def __init__(self) -> None:
        # this is just a sanity check: we don't want people to be able to
        # create additional instances of W_Void
        raise Exception("You cannot instantiate W_Void")

    def __repr__(self) -> str:
        return '<spy None>'

    def spy_unwrap(self, vm: 'SPyVM') -> None:
        return None

B.add('None', W_Void.__new__(W_Void))


@B.builtin_type('i32')
class W_I32(W_Object):
    value: fixedint.Int32

    def __init__(self, value: int | FixedInt) -> None:
        self.value = fixedint.Int32(value)

    def __repr__(self) -> str:
        return f'W_I32({self.value})'

    def spy_unwrap(self, vm: 'SPyVM') -> fixedint.Int32:
        return self.value


@B.builtin_type('i8')
class W_I8(W_Object):
    value: fixedint.Int8

    def __init__(self, value: int | FixedInt) -> None:
        self.value = fixedint.Int8(value)

    def __repr__(self) -> str:
        return f'W_I8({self.value})'

    def spy_unwrap(self, vm: 'SPyVM') -> fixedint.Int8:
        return self.value


@B.builtin_type('u8')
class W_U8(W_Object):
    value: fixedint.UInt8

    def __init__(self, value: int | FixedInt) -> None:
        self.value = fixedint.UInt8(value)

    def __repr__(self) -> str:
        return f'W_U8({self.value})'

    def spy_unwrap(self, vm: 'SPyVM') -> fixedint.UInt8:
        return self.value


@B.builtin_type('f64')
class W_F64(W_Object):
    value: float

    def __init__(self, value: float) -> None:
        assert type(value) is float
        self.value = value

    def __repr__(self) -> str:
        return f'W_F64({self.value})'

    def spy_unwrap(self, vm: 'SPyVM') -> float:
        return self.value


@B.builtin_type('bool')
class W_Bool(W_Object):
    value: bool

    def __init__(self, value: bool) -> None:
        # this is just a sanity check: we don't want people to be able to
        # create additional instances of W_Bool
        raise Exception("You cannot instantiate W_Bool. Use vm.wrap().")

    @staticmethod
    def _make_singleton(value: bool) -> 'W_Bool':
        w_obj = W_Bool.__new__(W_Bool)
        w_obj.value = value
        return w_obj

    def __repr__(self) -> str:
        return f'W_Bool({self.value})'

    def spy_unwrap(self, vm: 'SPyVM') -> bool:
        return self.value

    def not_(self, vm: 'SPyVM') -> 'W_Bool':
        if self.value:
            return B.w_False
        else:
            return B.w_True

B.add('True', W_Bool._make_singleton(True))
B.add('False', W_Bool._make_singleton(False))


@B.builtin_type('NotImplementedType') # XXX it should go to types?
class W_NotImplementedType(W_Object):

    def __init__(self) -> None:
        # this is just a sanity check: we don't want people to be able to
        # create additional instances
        raise Exception("You cannot instantiate W_NotImplementedType")

B.add('NotImplemented', W_NotImplementedType.__new__(W_NotImplementedType))



# The <dynamic> type
# ===================
#
# <dynamic> is special:
#
# - it's not a real type, in the sense that you cannot have an instance whose
#   type is `dynamic`
#
# - every class is considered to be a subclass of <dynamic>
#
# - conversion from T to <dynamic> always succeeds (like from T to <object>)
#
# - conversion from <dynamic> to T is always possible but it might fail at
#   runtime (like from <object> to T)
#
# From some point of view, <dynamic> is the twin of <object>, because it acts
# as if it were at the root of the type hierarchy. The biggest difference is
# how operators are dispatched: operations on <object> almost never succeeds,
# while operations on <dynamic> are dispatched to the actual dynamic
# types. For example:
#
#    x: object = 1
#    y: dynamic = 2
#    z: dynamic = 'hello'
#
#    x + 1 # compile-time error: cannot do `<object> + <i32>`
#    y + 1 # succeeds, but the dispatch is done at runtime
#    z + 1 # runtime error: cannot do `<i32> + <str>`
#
# Since it's a compile-time only concept, W_Dynamic is not a pyclass, but it's
# just an annotated version of W_Object, which @builtin_func knows how to deal
# with.

w_DynamicType = W_Type.from_pyclass(FQN('builtins::dynamic'), W_Object)
B.add('dynamic', w_DynamicType)
W_Dynamic = Annotated[W_Object, B.w_dynamic]
