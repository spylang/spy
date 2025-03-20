from typing import ClassVar, TYPE_CHECKING
from dataclasses import dataclass
from spy.location import Loc
from spy.errfmt import ErrorFormatter, Level, Annotation

if TYPE_CHECKING:
    from spy.vm.exc import W_Exception

def get_pyclass(etype: str) -> type['W_Exception']:
    from spy.vm.exc import (
        W_Exception, W_ParseError, W_TypeError, W_ImportError,
        W_ScopeError, W_NameError, W_ValueError
    )
    clsname = f'W_{etype}'
    return locals()[clsname]


class SPyError(Exception):
    w_exc: 'W_Exception'

    def __init__(
            self,
            message: str,
            *,
            etype: str = 'Exception'
    ) -> None:
        pyclass = get_pyclass(etype)
        self.w_exc = pyclass(message)
        super().__init__(message)

    @classmethod
    def simple(
            cls,
            primary: str,
            secondary: str,
            loc: Loc,
            *,
            etype: str = 'Exception'
    ) -> 'SPyError':
        err = cls(primary, etype=etype)
        err.add('error', secondary, loc)
        return err

    def match(self, pyclass: type['W_Exception']) -> bool:
        return isinstance(self.w_exc, pyclass)

    def __str__(self) -> str:
        return self.w_exc.format(use_colors=False)

    def add(self, level: Level, message: str, loc: Loc) -> None:
        self.w_exc.add(level, message, loc)

    def format(self, use_colors: bool = True) -> str:
        return self.w_exc.format(use_colors)

# ======

class SPyPanicError(SPyError):
    """
    Python-level exception raised when a WASM module aborts with a call to
    spy_panic().
    """
    #LEVEL = 'panic'

    def __init__(self, message: str, fname: str, lineno: int) -> None:
        super().__init__(message)
        self.filename = fname
        self.lineno = lineno
        if fname is not None:
            loc = Loc(fname, lineno, lineno, 1, -1)
            self.add('panic', '', loc)
