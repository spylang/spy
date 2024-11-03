from typing import ClassVar, TYPE_CHECKING
from spy.vm.object import W_Object, spytype

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM





@spytype('void')
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