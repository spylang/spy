from typing import ClassVar, TYPE_CHECKING, Any, Optional
from dataclasses import dataclass
from contextlib import contextmanager
from spy.location import Loc
from spy.errfmt import ErrorFormatter, Level, Annotation

if TYPE_CHECKING:
    from spy.vm.exc import W_Exception

def get_pyclass(etype: str) -> type['W_Exception']:
    """
    Perform a lazy lookup of app-level exception classes.

    Example:
        get_pyclass('W_TypeError') --> spy.vm.exc.W_TypeError
    """
    import spy.vm.exc
    assert etype.startswith('W_')
    return getattr(spy.vm.exc, etype)


class SPyError(Exception):
    etype: str
    w_exc: 'W_Exception'

    def __init__(self, etype: str, message: str) -> None:
        pyclass = get_pyclass(etype)
        self.etype = etype
        self.w_exc = pyclass(message)
        super().__init__(message)

    @classmethod
    def simple(cls, etype: str, primary: str,
               secondary: str,loc: Loc) -> 'SPyError':
        err = cls(etype, primary)
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

    @contextmanager
    @staticmethod
    def raises(etype: str, match: Optional[str]=None) -> Any:
        """
        Equivalent to pytest.raises(SPyError, ...), but also checks the
        etype.
        """
        import pytest
        with pytest.raises(SPyError, match=match) as excinfo:
            yield excinfo
        exc = excinfo.value
        assert isinstance(exc, SPyError)
        if exc.etype != etype:
            msg = f"Expected SPyError of type {etype}, but got {exc.etype}"
            pytest.fail(msg)

# ======

class SPyPanicError(Exception):
    """
    Python-level exception raised when a WASM module aborts with a call to
    spy_panic().
    """
    #LEVEL = 'panic'

    def __init__(self, message: str, fname: str, lineno: int) -> None:
        super().__init__(message)
        self.filename = fname
        self.lineno = lineno
        ## if fname is not None:
        ##     loc = Loc(fname, lineno, lineno, 1, -1)
        ##     self.add('panic', '', loc)
