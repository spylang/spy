from typing import TYPE_CHECKING, Optional, Sequence
from collections import Counter, defaultdict
from spy.vm.object import W_Object
from spy.vm.function import W_Func
from spy.textbuilder import Color
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

ARGS_W = Sequence[W_Object]
KEY = tuple[W_Func, tuple[W_Object,...]]

DEBUG = False

class BlueCache:
    """
    Store and record the results of blue functions.

    Currently this is very inefficient, because for every W_Func it records a
    list of calls, and then during lookup it does a linear search.

    We should use a SPy dict, as soon as we have it.
    """
    vm: 'SPyVM'
    data: dict[KEY, W_Object]

    def __init__(self, vm: 'SPyVM'):
        self.vm = vm
        self.data = {} # defaultdict(list)

    def record(self, w_func: W_Func, args_w: ARGS_W, w_result: W_Object) ->None:
        args_key = tuple(w_arg.spy_key(self.vm) for w_arg in args_w)
        key = (w_func, args_key)
        self.data[key] = w_result

    def lookup(self, w_func: W_Func, args_w: ARGS_W) -> Optional[W_Object]:
        args_key = tuple(w_arg.spy_key(self.vm) for w_arg in args_w)
        key = (w_func, args_key)
        w_res = self.data.get(key)
        if DEBUG:
            print(f'BlueCache.lookup: {w_func.fqn}, {args_w} -> {w_res}')
        return w_res

    def pp(self) -> None:
        c: Counter[W_Func] = Counter()
        for (w_func, args_w), w_result in self.data.items():
            c[w_func] += 1
        print()
        print('=== vm.bluecache ===')
        print('Entries | Function')
        for w_func, n in c.most_common():
            print(f'{n:7d} | {w_func.fqn}')
