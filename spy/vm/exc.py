# NOTE: W_Exception is NOT a subclass of Exception. If you want to raise a
# W_Exception, you need to wrap it into SPyError.

import traceback
from dataclasses import dataclass
from types import FrameType, TracebackType
from typing import TYPE_CHECKING, Annotated, Iterable, Literal, Optional

from spy.errfmt import Annotation, ErrorFormatter, Level
from spy.fqn import FQN
from spy.location import Loc
from spy.vm.b import BUILTINS, TYPES
from spy.vm.builtin import builtin_method
from spy.vm.object import W_Object, W_Type
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.primitive import W_Bool
from spy.vm.str import W_Str

if TYPE_CHECKING:
    from spy.vm.astframe import AbstractFrame
    from spy.vm.vm import SPyVM

FrameKind = Literal["astframe", "modframe", "classframe", "dopplerframe"]


class FrameInfo:
    def __init__(self, spyframe: "AbstractFrame") -> None:
        self.spyframe = spyframe
        self.loc = spyframe.loc

    @property
    def kind(self) -> FrameKind:
        k = self.spyframe.__class__.__name__.lower()
        assert k in FrameKind.__args__  # type: ignore
        return k  # type: ignore

    @property
    def fqn(self) -> FQN:
        return self.spyframe.ns


@TYPES.builtin_type("TracebackType")
class W_Traceback(W_Object):
    """
    Traceback of a SPy exception.

    Note that this has a different API than CPython 'traceback' object. It's more
    similar to CPython 'traceback.StackSummary' class.
    """

    entries: list[FrameInfo]

    def __init__(self, entries: list[FrameInfo]) -> None:
        self.entries = entries

    def __repr__(self) -> str:
        if len(self.entries) == 0:
            return f"<spy traceback (empty)>"
        elif len(self.entries) == 1:
            a = self.entries[0].fqn
            return f"<spy traceback ...{a}>"
        else:
            a = self.entries[0].fqn
            b = self.entries[-1].fqn
            return f"<spy traceback: {a}... {b}>"

    @classmethod
    def from_py_traceback(cls, tb: TracebackType) -> "W_Traceback":
        """
        Create a StackSummary of the applevel SPy frames from an interp-level
        Python 'traceback' object.
        """
        frames = traceback._walk_tb_with_full_positions(tb)  # type: ignore
        return cls._from_py_frames(frames)

    @classmethod
    def from_py_frame(cls, frame: FrameType) -> "W_Traceback":
        frames = list(traceback.walk_stack(frame))
        frames.reverse()
        return cls._from_py_frames(frames)

    @classmethod
    def _from_py_frames(cls, frames: Iterable[tuple[FrameType, int]]) -> "W_Traceback":
        from spy.doppler import DopplerFrame
        from spy.vm.astframe import ASTFrame
        from spy.vm.classframe import ClassFrame
        from spy.vm.modframe import ModFrame

        # Imagine to have this SPy code:
        #     def main() -> None:
        #         return foo()
        #
        #     def foo() -> None:
        #         raise ValueError
        #
        #
        # The "raise" statement raises a SPyError which captures the interp-level
        # traceback. The traceback looks more or less like this (after hiding many
        # irrelevant frames):
        #
        # Most recent calls last:
        #   real_main (in cli.py)
        #   [...]
        #   ASTFrame.run                       applevel frame for `x::main`
        #   ASTFrame.exec_stmt                     ast.Return(ast.Call(...))
        #   ASTFrame.exec_stmt_Stmt_Return
        #   ASTFrame.eval_expr                     ast.Call(...)
        #   ASTFrame.eval_expr_Call
        #   [...]
        #   ASTFrame.run                       applevel frame for `x::foo`
        #   ASTFrame.exec_stmt                     ast.Raise(...)
        #   ASTFrame.exec_stmt_Raise
        #   [...]
        #   w_raise (in raiseop.py)
        #
        #   When we encounter ASTFrame.run, we record an app-level SPy frame.
        #   When we encounter exec_stmt or eval_expr, we set a more precise loc info
        #   for the last recorded frame.
        entries = []
        for frame, lineno in frames:
            if frame.f_code in (
                ASTFrame.run.__code__,
                ModFrame.run.__code__,
                ClassFrame.run.__code__,
                DopplerFrame.redshift.__code__,
            ):
                # found an applevel frame
                spyframe = frame.f_locals["self"]
                entries.append(FrameInfo(spyframe))

            elif frame.f_code in (
                ASTFrame.eval_expr.__code__,
                DopplerFrame.eval_expr.__code__,
            ):
                # update last frame with more precise loc info
                expr = frame.f_locals["expr"]
                entries[-1].loc = expr.loc

            elif frame.f_code is ASTFrame.exec_stmt.__code__:
                # update last frame with more precise loc info
                stmt = frame.f_locals["stmt"]
                entries[-1].loc = stmt.loc

        return cls(entries)

    def pp(self) -> None:
        from spy.errfmt import ErrorFormatter

        fmt = ErrorFormatter(use_colors=True)
        fmt.emit_traceback(self)
        print(fmt.build())


@BUILTINS.builtin_type("Exception")
class W_Exception(W_Object):
    message: str
    annotations: list[Annotation]
    w_tb: Optional[W_Traceback]

    # interp-level interface

    def __init__(self, message: str) -> None:
        assert isinstance(message, str)
        self.message = message
        self.annotations = []
        self.w_tb = None

    def with_traceback(self, py_tb: TracebackType) -> None:
        self.w_tb = W_Traceback.from_py_traceback(py_tb)

    def add(self, level: Level, message: str, loc: Loc) -> None:
        self.annotations.append(Annotation(level, message, loc))

    def format(self, use_colors: bool = True) -> str:
        return ErrorFormatter.format_exception(self, use_colors=use_colors)

    def __repr__(self) -> str:
        cls = self.__class__.__name__
        return f"{cls}({self.message!r})"

    # app-level interface

    @builtin_method("__new__", color="blue", kind="metafunc")
    @staticmethod
    def w_NEW(vm: "SPyVM", wam_cls: W_MetaArg, *args_wam: W_MetaArg) -> W_OpSpec:
        # we cannot use the default __new__ because we want to pass w_cls
        _args_wam: list[W_MetaArg] = list(args_wam) or [
            W_MetaArg.from_w_obj(vm, vm.wrap(""))
        ]
        w_cls = wam_cls.w_blueval
        assert isinstance(w_cls, W_Type)
        fqn = w_cls.fqn
        T = Annotated[W_Exception, w_cls]

        # the whole "raise Exception(...)" is a bit of a hack at the moment:
        # the C backend can raise only BLUE exceptions, so here we make sure
        # that Exception("...") is blue
        @vm.register_builtin_func(fqn, "__new__", color="blue")
        def w_new(vm: "SPyVM", w_cls: W_Type, w_message: W_Str) -> T:
            pyclass = w_cls.pyclass
            assert issubclass(pyclass, W_Exception)
            message = vm.unwrap_str(w_message)
            return pyclass(message)

        return W_OpSpec(w_new, [wam_cls] + _args_wam)

    @builtin_method("__eq__", color="blue", kind="metafunc")
    @staticmethod
    def w_EQ(vm: "SPyVM", wam_a: W_MetaArg, wam_b: W_MetaArg) -> W_OpSpec:
        from spy.vm.opspec import W_OpSpec

        w_atype = wam_a.w_static_T
        w_btype = wam_b.w_static_T

        # If different exception types, return null implementation
        if w_atype is not w_btype:
            return W_OpSpec.NULL

        @vm.register_builtin_func(w_atype.fqn)
        def w_eq(vm: "SPyVM", w_e1: W_Exception, w_e2: W_Exception) -> W_Bool:
            res = w_e1.message == w_e2.message and w_e1.annotations == w_e2.annotations
            return vm.wrap(bool(res))

        return W_OpSpec(w_eq)

    @builtin_method("__ne__", color="blue", kind="metafunc")
    @staticmethod
    def w_NE(vm: "SPyVM", wam_a: W_MetaArg, wam_b: W_MetaArg) -> W_OpSpec:
        from spy.vm.opspec import W_OpSpec

        w_atype = wam_a.w_static_T
        w_btype = wam_b.w_static_T

        # If different exception types, return null implementation
        if w_atype is not w_btype:
            return W_OpSpec.NULL

        @vm.register_builtin_func(w_atype.fqn)
        def w_ne(vm: "SPyVM", w_e1: W_Exception, w_e2: W_Exception) -> W_Bool:
            res = not (
                w_e1.message == w_e2.message and w_e1.annotations == w_e2.annotations
            )
            return vm.wrap(bool(res))

        return W_OpSpec(w_ne)


@BUILTINS.builtin_type("StaticError")
class W_StaticError(W_Exception):
    """
    Static errors are those who can be turned into lazy errors during
    redshifting.

    All the other exceptions are immediately reported and abort redshiting.
    """

    pass


@BUILTINS.builtin_type("TypeError")
class W_TypeError(W_StaticError):
    """
    Note that TypeError is a subclass of StaticError
    """

    pass


@BUILTINS.builtin_type("ValueError")
class W_ValueError(W_Exception):
    pass


@BUILTINS.builtin_type("IndexError")
class W_IndexError(W_Exception):
    pass


@BUILTINS.builtin_type("ParseError")
class W_ParseError(W_Exception):
    pass


@BUILTINS.builtin_type("ImportError")
class W_ImportError(W_Exception):
    pass


@BUILTINS.builtin_type("ScopeError")
class W_ScopeError(W_Exception):
    pass


@BUILTINS.builtin_type("NameError")
class W_NameError(W_Exception):
    pass


@BUILTINS.builtin_type("PanicError")
class W_PanicError(W_Exception):
    pass


@BUILTINS.builtin_type("ZeroDivisionError")
class W_ZeroDivisionError(W_Exception):
    pass


@BUILTINS.builtin_type("AssertionError")
class W_AssertionError(W_Exception):
    pass


@BUILTINS.builtin_type("KeyError")
class W_KeyError(W_Exception):
    pass


@BUILTINS.builtin_type("WIP")
class W_WIP(W_Exception):
    """
    Raised when something is supposed to work but has not been implemented yet
    """


@TYPES.builtin_type("SPdbQuit")
class W_SPdbQuit(W_Exception):
    """
    Raised when doing 'quit' from (spdb) prompt
    """
