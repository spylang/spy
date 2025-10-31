import linecache
import sys
import traceback
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from spy.fqn import FQN
from spy.location import Loc
from spy.textbuilder import TextBuilder
from spy.vm.astframe import ASTFrame
from spy.vm.builtin import builtin_method
from spy.vm.object import W_Object

from . import TRACEBACK

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@dataclass
class FrameSummary:
    kind: Literal["py", "spy"]
    func: str | FQN  # str for "py", FQN for "spy"
    loc: Loc

    @classmethod
    def from_py_frame(cls, frame) -> "FrameSummary":
        py_stack = [(frame, frame.f_lineno)]
        py_stack_summ = traceback.StackSummary.extract(py_stack)
        fs = py_stack_summ[0]  # this is CPython's FrameSummary
        if fs.colno is None:
            col_start = 0
            col_end = -1
        else:
            col_start = fs.colno
            col_end = fs.end_colno
        loc = Loc(fs.filename, fs.lineno, fs.lineno, col_start, col_end)
        return cls("py", fs.name, loc)


@TRACEBACK.builtin_type("StackSummary")
class W_StackSummary(W_Object):
    entries: list[FrameSummary]

    def __init__(self, entries: list[FrameSummary]) -> None:
        self.entries = entries

    @classmethod
    def _from_frames(cls, frames) -> "W_StackSummary":
        entries = []
        for frame, lineno in frames:
            # entries.append(FrameSummary.from_py_frame(frame))
            if frame.f_code is ASTFrame.run.__code__:
                # For each ASTFrame.run we have a SPy frame
                spyframe = frame.f_locals["self"]
                entries.append(FrameSummary("spy", spyframe.w_func.fqn, spyframe.loc))
        return cls(entries)

    @classmethod
    def from_traceback(cls, tb) -> "W_StackSummary":
        """
        Create a StackSummary of the applevel SPy frames from an interp-level
        Python 'traceback' object
        """
        frames = traceback._walk_tb_with_full_positions(tb)
        return cls._from_frames(frames)

    @classmethod
    def from_pystack(cls) -> "W_StackSummary":
        """
        Create a StackSummary of the applevel SPy frames from the interp-level
        Python frames.
        """
        start_frame = sys._getframe(1)  # Start from the caller's frame
        frames = traceback.walk_stack(start_frame)
        w_res = cls._from_frames(frames)
        w_res.entries.reverse()
        return w_res


@TRACEBACK.builtin_func
def w_extract_stack(vm: "SPyVM") -> W_StackSummary:
    return W_StackSummary.from_pystack()
