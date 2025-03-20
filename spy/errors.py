from typing import ClassVar, TYPE_CHECKING
from dataclasses import dataclass
from spy.location import Loc
from spy.errfmt import ErrorFormatter, Level, Annotation


class SPyError(Exception):
    LEVEL: ClassVar[Level] = 'error'

    message: str
    annotations: list[Annotation]

    def __init__(self, message: str) -> None:
        self.message = message
        self.annotations = []
        super().__init__(message)

    @classmethod
    def simple(cls, primary: str, secondary: str, loc: Loc) -> 'SPyError':
        err = cls(primary)
        err.add('error', secondary, loc)
        return err

    def __str__(self) -> str:
        return self.format(use_colors=False)

    def add(self, level: Level, message: str, loc: Loc) -> None:
        self.annotations.append(Annotation(level, message, loc))

    def format(self, use_colors: bool = True) -> str:
        fmt = ErrorFormatter(self, use_colors)
        fmt.emit_message(self.LEVEL, self.message)
        for ann in self.annotations:
            fmt.emit_annotation(ann)
        return fmt.build()


class SPyParseError(SPyError):
    pass


class SPyTypeError(SPyError):
    pass


class SPyImportError(SPyError):
    pass


class SPyScopeError(SPyError):
    """
    Raised if a variable declaration redeclares or shadows a name, see
    symtable.py
    """

class SPyNameError(SPyError):
    """
    Raised if we try to access a variable which is not defined
    """

# ======

class SPyRuntimeError(Exception):
    pass

class SPyRuntimeAbort(SPyRuntimeError):
    pass


class SPyPanicError(SPyError):
    """
    Python-level exception raised when a WASM module aborts with a call to
    spy_panic().
    """
    LEVEL = 'panic'

    def __init__(self, message: str, fname: str, lineno: int) -> None:
        super().__init__(message)
        self.filename = fname
        self.lineno = lineno
        if fname is not None:
            loc = Loc(fname, lineno, lineno, 1, -1)
            self.add('panic', '', loc)
