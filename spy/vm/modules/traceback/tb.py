import linecache
import sys
import traceback
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from spy.doppler import DopplerFrame
from spy.fqn import FQN
from spy.location import Loc
from spy.textbuilder import TextBuilder
from spy.vm.astframe import ASTFrame
from spy.vm.builtin import builtin_method
from spy.vm.classframe import ClassFrame
from spy.vm.modframe import ModFrame
from spy.vm.object import W_Object

from . import TRACEBACK

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@dataclass
class FrameSummary:
    kind: Literal["astframe", "modframe", "classframe", "dopplerframe"]
    func: FQN
    loc: Loc


@TRACEBACK.builtin_type("StackSummary")
class W_StackSummary(W_Object):
    entries: list[FrameSummary]

    def __init__(self, entries: list[FrameSummary]) -> None:
        self.entries = entries

    @classmethod
    def from_traceback(cls, tb) -> "W_StackSummary":
        """
        Create a StackSummary of the applevel SPy frames from an interp-level
        Python 'traceback' object.
        """
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
        frames = traceback._walk_tb_with_full_positions(tb)
        for frame, lineno in frames:
            # ==== record applevel frame ====
            if frame.f_code is ASTFrame.run.__code__:
                spyframe = frame.f_locals["self"]
                fqn = spyframe.w_func.fqn
                loc = spyframe.w_func.funcdef.loc
                entries.append(FrameSummary("astframe", fqn, loc))

            elif frame.f_code is ModFrame.run.__code__:
                # record the applevel frame
                spyframe = frame.f_locals["self"]
                fqn = spyframe.ns
                loc = spyframe.mod.loc
                entries.append(FrameSummary("modframe", fqn, loc))

            elif frame.f_code is ClassFrame.run.__code__:
                # record the applevel frame
                spyframe = frame.f_locals["self"]
                fqn = spyframe.ns
                loc = spyframe.classdef.loc
                entries.append(FrameSummary("classframe", fqn, loc))

            elif frame.f_code is DopplerFrame.redshift.__code__:
                # record the applevel frame
                spyframe = frame.f_locals["self"]
                fqn = spyframe.w_func.fqn
                loc = spyframe.w_func.funcdef.loc
                entries.append(FrameSummary("dopplerframe", fqn, loc))

            # ==== update last frame with more precise loc info ====
            elif frame.f_code is ASTFrame.eval_expr.__code__:
                expr = frame.f_locals["expr"]
                entries[-1].loc = expr.loc

            elif frame.f_code is ASTFrame.exec_stmt.__code__:
                # update last frame with more precise loc info
                stmt = frame.f_locals["stmt"]
                entries[-1].loc = stmt.loc

        return cls(entries)
