"""
The SPy debugger ("spy pdb")
"""

import cmd
import pdb
import sys
from typing import TYPE_CHECKING, Annotated, Literal

from spy.doppler import DopplerFrame
from spy.errfmt import ErrorFormatter
from spy.vm.astframe import ASTFrame
from spy.vm.b import BUILTINS
from spy.vm.classframe import ClassFrame
from spy.vm.debugger.longlist import print_longlist
from spy.vm.exc import FrameInfo, W_Traceback
from spy.vm.modframe import ModFrame
from spy.vm.w import W_Object

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@BUILTINS.builtin_func
def w_breakpoint(vm: "SPyVM") -> None:
    # generate a fake traceback
    pyframe = sys._getframe().f_back
    assert pyframe is not None
    w_tb = W_Traceback.from_py_frame(pyframe)

    spdb = SPdb(w_tb)
    spdb.interaction()


class SPdb(cmd.Cmd):
    prompt = "(spdb🥸) "

    def __init__(self, w_tb: W_Traceback) -> None:
        super().__init__()
        self.w_tb = w_tb
        self.curindex = -1  # currently selected frame

    def interaction(self) -> None:
        print("---app-level spdb---")
        last = len(self.w_tb.entries) - 1
        self.select_frame(last)
        self.cmdloop()

    def select_frame(self, i: int) -> None:
        assert 0 <= i < len(self.w_tb.entries)
        if self.curindex != i:
            self.curindex = i
            self.print_frame_info(i)

    def get_curframe(self) -> FrameInfo:
        return self.w_tb.entries[self.curindex]

    def print_frame_info(self, i: int) -> None:
        f = self.w_tb.entries[i]
        errfmt = ErrorFormatter(use_colors=True)
        errfmt.emit_frameinfo(f, index=i)
        print(errfmt.build(), end="")

    def error(self, msg: str) -> None:
        print("***", msg)

    def do_quit(self, arg: str) -> bool:
        return True

    do_q = do_quit

    def do_where(self, arg: str) -> None:
        """w(here)

        Print a stack trace, with the most recent frame at the bottom.
        """
        errfmt = ErrorFormatter(use_colors=True)
        for i, f in enumerate(self.w_tb.entries):
            errfmt.emit_frameinfo(f, index=i, is_current=(i == self.curindex))
        print(errfmt.build(), end="")

    do_w = do_where
    do_bt = do_where

    def do_up(self, arg: str) -> None:
        """u(p) [count]

        Move the current frame count (default one) levels up in the
        stack trace (to an older frame).
        """
        if self.curindex == 0:
            self.error("Oldest frame")
            return
        try:
            count = int(arg or 1)
        except ValueError:
            self.error("Invalid frame count (%s)" % arg)
            return
        if count < 0:
            newframe = 0
        else:
            newframe = max(0, self.curindex - count)
        self.select_frame(newframe)

    do_u = do_up

    def do_down(self, arg: str) -> None:
        """d(own) [count]

        Move the current frame count (default one) levels down in the
        stack trace (to a newer frame).
        """
        if self.curindex + 1 == len(self.w_tb.entries):
            self.error("Newest frame")
            return
        try:
            count = int(arg or 1)
        except ValueError:
            self.error("Invalid frame count (%s)" % arg)
            return
        if count < 0:
            newframe = len(self.w_tb.entries) - 1
        else:
            newframe = min(len(self.w_tb.entries) - 1, self.curindex + count)
        self.select_frame(newframe)

    do_d = do_down

    def do_longlist(self, arg: str) -> None:
        """l | ll | list | longlist

        List the whole source code for the current function or frame.
        """
        f = self.get_curframe()
        if f.kind == "astframe":
            spyframe = f.spyframe
            assert isinstance(spyframe, ASTFrame)
            # Get the function location and current location
            func_loc = spyframe.loc
            cur_loc = f.loc
            print_longlist(func_loc, cur_loc)

    do_list = do_longlist
    do_l = do_longlist
    do_ll = do_longlist
