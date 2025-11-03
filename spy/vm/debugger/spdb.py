"""
The SPy debugger ("spy pdb")
"""

import cmd
import pdb
import sys
from typing import TYPE_CHECKING, Annotated, Literal

from spy.vm.b import BUILTINS
from spy.vm.exc import W_Traceback
from spy.vm.w import W_Object

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@BUILTINS.builtin_func
def w_breakpoint(vm: "SPyVM") -> None:
    # generate a fake traceback
    pyframe = sys._getframe().f_back
    w_tb = W_Traceback.from_py_frame(pyframe)
    breakpoint()

    spdb = SPdb(w_tb)
    spdb.cmdloop()


class SPdb(cmd.Cmd):
    prompt = "(spdb🥸) "

    def __init__(self, w_tb: W_Traceback) -> None:
        super().__init__()
        self.w_tb = w_tb

    def do_quit(self, arg):
        return True

    do_q = do_quit

    def do_list(self, arg):
        breakpoint()
        print("list", arg)

    do_l = do_list
