from typing import ClassVar, TYPE_CHECKING
import fixedint
from spy.vm.object import W_Object
from spy.vm.b import B
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

@B.builtin_type('void')
class W_Void(W_Object):
    """
    Equivalent of Python's NoneType.

    This is a singleton: there should be only one instance of this class,
    which is w_None.
    """

    _w_singleton: ClassVar['W_Void']

    def __init__(self) -> None:
        # this is just a sanity check: we don't want people to be able to
        # create additional instances of W_Void
        raise Exception("You cannot instantiate W_Void")

    def __repr__(self) -> str:
        return '<spy None>'

    def spy_unwrap(self, vm: 'SPyVM') -> None:
        return None

W_Void._w_singleton = W_Void.__new__(W_Void)

@B.builtin_type('i32')
class W_I32(W_Object):
    value: fixedint.Int32

    def __init__(self, value: int | fixedint.Int32) -> None:
        assert type(value) in (int, fixedint.Int32)
        self.value = fixedint.Int32(value)

    def __repr__(self) -> str:
        return f'W_I32({self.value})'

    def spy_unwrap(self, vm: 'SPyVM') -> fixedint.Int32:
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
    #
    _w_singleton_True: ClassVar['W_Bool']
    _w_singleton_False: ClassVar['W_Bool']

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
            return W_Bool._w_singleton_False
        else:
            return W_Bool._w_singleton_True

W_Bool._w_singleton_True = W_Bool._make_singleton(True)
W_Bool._w_singleton_False = W_Bool._make_singleton(False)


@B.builtin_type('NotImplementedType') # XXX it should go to types?
class W_NotImplementedType(W_Object):
    _w_singleton: ClassVar['W_NotImplementedType']

    def __init__(self) -> None:
        # this is just a sanity check: we don't want people to be able to
        # create additional instances
        raise Exception("You cannot instantiate W_NotImplementedType")

W_NotImplementedType._w_singleton = (
    W_NotImplementedType.__new__(W_NotImplementedType)
)




B.add('NotImplemented', W_NotImplementedType._w_singleton)
B.add('None', W_Void._w_singleton)
B.add('True', W_Bool._w_singleton_True)
B.add('False', W_Bool._w_singleton_False)
