from collections import defaultdict
from typing import TYPE_CHECKING, Optional
from spy.fqn import QN
from spy.vm.object import W_Object
from spy.vm.function import W_Func
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

ARGS_W = list[W_Object]
ENTRY = tuple[ARGS_W, W_Object]

class BlueCache:
    """
    Store and record the results of blue functions.

    Currently this is very inefficient, because for every W_Func it records a
    list of calls, and then during lookup it does a linear search.

    We should use a SPy dict, as soon as we have it.
    """
    vm: 'SPyVM'
    data: defaultdict[W_Func, list[ENTRY]]

    def __init__(self, vm: 'SPyVM'):
        self.vm = vm
        self.data = defaultdict(list)

    def record(self, w_func: W_Func, args_w: ARGS_W, w_result: W_Object) ->None:
        entry = (args_w, w_result)
        self.data[w_func].append(entry)

    def lookup(self, w_func: W_Func, got_args_w: ARGS_W) -> Optional[W_Object]:
        entries = self.data[w_func]
        ## if w_func.qn == QN('operator::CALL_METHOD'):
        ##     import pdb;pdb.set_trace()
        for args_w, w_result in entries:
            if self.args_w_eq(args_w, got_args_w):
                return w_result
        return None

    def args_w_eq(self, args1_w: ARGS_W, args2_w: ARGS_W) -> bool:
        if len(args1_w) != len(args2_w):
            return False
        for w_a, w_b in zip(args1_w, args2_w):
            if self.vm.is_False(self.vm.universal_eq(w_a, w_b)):
                return False
        return True
