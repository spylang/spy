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

    def print(self) -> None:
        tb = TextBuilder(use_colors=True)

        tb.wl("Traceback (most recent call last):")

        for e in self.entries:
            assert e.kind == "spy"
            tb.wl(
                f'  File "{e.loc.filename}", line {e.loc.line_start}, in {e.func}',
            )
            line = linecache.getline(e.loc.filename, e.loc.line_start).strip()
            if line:
                tb.wl(f"    {line}")

        tb.wl()
        print(tb.build())

    @builtin_method("print")
    @staticmethod
    def w_print(vm: "SPyVM", w_self: "W_StackSummary") -> None:
        w_self.print()


@TRACEBACK.builtin_func
def w_extract_stack(vm: "SPyVM") -> W_StackSummary:
    entries = []

    start_frame = sys._getframe(1)  # Start from the caller's frame
    for frame, lineno in traceback.walk_stack(start_frame):
        # entries.append(FrameSummary.from_py_frame(frame))
        if frame.f_code is ASTFrame.run.__code__:
            # For each ASTFrame.run we have a SPy frame
            spyframe = frame.f_locals["self"]
            entries.append(FrameSummary("spy", spyframe.w_func.fqn, spyframe.loc))

    entries.reverse()
    return W_StackSummary(entries)
