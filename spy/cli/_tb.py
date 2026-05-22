import os
import sys
from inspect import getframeinfo
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import FrameType, TracebackType

TB_ENV_KEY_NAME = "SPY_HIDE_MAGIC_FRAMES"


def _is_magic_dispatch_frame(f: FrameType) -> bool:
    info = getframeinfo(f)
    return "util.py" in info.filename and info.function == "magic_dispatch"


def _is_magic_dispatch_call(f: FrameType) -> bool:
    info = getframeinfo(f)
    return "magic_dispatch" in info.code_context[0]


def tb_hide_magic_frames_maybe() -> TracebackType:
    # Get exception info, and return a traceback with magic_dispatch() frames
    # and calls to magic_dispatch() omitted, depending on an
    # environment variable
    info = sys.exc_info()
    head_tb = info[2]
    tb = head_tb

    if os.environ[TB_ENV_KEY_NAME] == "1":
        while tb.tb_next is not None:
            if tb.tb_next.tb_next is not None:
                next_frame = tb.tb_next.tb_frame
                if _is_magic_dispatch_frame(next_frame) or _is_magic_dispatch_call(
                    next_frame
                ):
                    tb.tb_next = tb.tb_next.tb_next  # skip the frame
                else:
                    tb = tb.tb_next
            else:
                tb = tb.tb_next

    return head_tb
