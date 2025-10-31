from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Optional

from spy.errfmt import Level
from spy.location import Loc

if TYPE_CHECKING:
    from spy.vm.exc import W_Exception


def get_pyclass(etype: str) -> type["W_Exception"]:
    """
    Perform a lazy lookup of app-level exception classes.

    Example:
        get_pyclass('W_TypeError') --> spy.vm.exc.W_TypeError
    """
    import spy.vm.exc

    assert etype.startswith("W_")
    return getattr(spy.vm.exc, etype)


class SPyError(Exception):
    etype: str
    w_exc: "W_Exception"

    def __init__(self, etype: str, message: str) -> None:
        pyclass = get_pyclass(etype)
        self.etype = etype
        self.w_exc = pyclass(message)
        super().__init__(message)

    @classmethod
    def simple(cls, etype: str, primary: str, secondary: str, loc: Loc) -> "SPyError":
        err = cls(etype, primary)
        err.add("error", secondary, loc)
        return err

    def match(self, pyclass: type["W_Exception"]) -> bool:
        return isinstance(self.w_exc, pyclass)

    def __str__(self) -> str:
        return self.w_exc.format(use_colors=False)

    def add(self, level: Level, message: str, loc: Loc) -> None:
        self.w_exc.add(level, message, loc)

    def add_location_maybe(self, loc: Loc) -> None:
        """
        Add "generic" location info to the exception, but only if there
        isn't any yet.
        """
        self.w_exc.add_location_maybe(loc)

    def format(self, use_colors: bool = True) -> str:
        from spy.vm.modules.traceback.tb import W_StackSummary

        w_stack_summary = W_StackSummary.from_traceback(self.__traceback__)
        return self.w_exc.format(use_colors, w_stack_summary=w_stack_summary)

    @contextmanager
    @staticmethod
    def raises(etype: str, match: Optional[str] = None) -> Any:
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


def WIP(message: str) -> SPyError:
    return SPyError("W_WIP", message)
