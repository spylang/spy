from collections import defaultdict
import operator
from typing import TYPE_CHECKING, Optional, Sequence
from spy.vm.object import W_Object
from spy.vm.function import W_Func
from spy.textbuilder import Color
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

ARGS_W = Sequence[W_Object]
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

    def pp(self, funcname: Optional[str] = None) -> None:
        if funcname:
            for w_func, entries in self.data.items():
                if funcname in str(w_func.fqn):
                    self._pp_one(w_func, entries)
        else:
            items = sorted(self.data.items(), key=lambda x: len(x[1]))
            for w_func, entries in items:
                n = len(entries)
                print(f'{n:4d} {w_func.fqn}')

    def _pp_one(self, w_func: W_Func, entries: list[ENTRY]) -> None:
        print(w_func.fqn)
        for args_w, w_result in entries:
            args = ', '.join([str(w_arg) for w_arg in args_w])
            res = str(w_result)
            print(Color.set('red', args), Color.set('yellow', res))
