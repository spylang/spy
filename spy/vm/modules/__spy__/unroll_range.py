from typing import TYPE_CHECKING

from spy.vm.modules.__spy__ import SPY
from spy.vm.object import W_Object
from spy.vm.primitive import W_I32

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@SPY.builtin_type("UnrollRange")
class W_UnrollRange(W_Object):
    n: int

    def __init__(self, n: int) -> None:
        self.n = n


@SPY.builtin_func("UNROLL_RANGE", color="blue")
def w_UNROLL_RANGE(vm: "SPyVM", w_n: W_I32) -> W_UnrollRange:
    n = vm.unwrap_i32(w_n)
    return W_UnrollRange(n)
