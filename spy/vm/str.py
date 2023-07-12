from typing import TYPE_CHECKING, Any
from spy.vm.object import W_Object, spytype
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM



@spytype('str')
class W_str(W_Object):
    """
    An unicode string.

    Internally, it is represented as UTF-8.
    """
    utf8_bytes: bytes

    def __init__(self, s: str) -> None:
        self.utf8_bytes = s.encode('utf-8')

    def _as_str(self) -> str:
        return self.utf8_bytes.decode('utf-8')

    def __repr__(self) -> str:
        s = self._as_str()
        return f'W_str({s!r})'

    def spy_unwrap(self, vm: 'SPyVM') -> Any:
        return self._as_str()
