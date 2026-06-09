import os
import sys
from inspect import getframeinfo
from types import FrameType, TracebackType


def _is_magic_dispatch_frame(f: FrameType) -> bool:
    info = getframeinfo(f)
    return "util.py" in info.filename and info.function == "magic_dispatch"


def _is_magic_dispatch_call(f: FrameType) -> bool:
    """
    Check whether the string `magic_dispatch(` is in the line of code that's
    present the current frame of a traceback. info.code_context is an array of
    strings of the lines of code "around" the line being executed.
    info.index is the index of the line currently being executed
    """
    info = getframeinfo(f)
    return (context := info.code_context) is not None and "magic_dispatch(" in context[
        info.index
    ]


def tb_hide_magic_frames_maybe() -> TracebackType:
    # Get exception info, and return a traceback with magic_dispatch() frames
    # and calls to magic_dispatch() omitted, depending on an
    # environment variable
    info = sys.exc_info()
    head_tb = info[2]
    assert head_tb is not None
    tb = head_tb

    if (env_val := os.getenv("SPY_SHOW_MAGIC_FRAMES")) and int(env_val) == 1:
        # We actually want to show all the magic frames; return stack unchanged
        pass
    else:
        while tb.tb_next is not None:
            if tb.tb_next.tb_next is not None:
                next_frame = tb.tb_next.tb_frame
                if _is_magic_dispatch_frame(next_frame) or _is_magic_dispatch_call(
                    next_frame
                ):
                    tb.tb_next = tb.tb_next.tb_next  # skip the magic frame
                else:
                    tb = tb.tb_next
            else:
                assert (
                    tb.tb_next is not None
                )  # make mypy happy; we know this is true from the while statement above
                tb = tb.tb_next

    return head_tb
