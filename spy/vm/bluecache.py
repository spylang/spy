from typing import TYPE_CHECKING, Optional, Sequence, Any
import itertools
from collections import Counter, defaultdict
from spy.vm.object import W_Object
from spy.vm.function import W_Func
from spy.textbuilder import Color
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

DEBUG = False

ARGS_W = Sequence[W_Object]
ARGS_KEY = tuple[W_Object, ...]
KEY = tuple[W_Func, ARGS_KEY]

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
        self.data = {}

    def record(self, w_func: W_Func, args_w: ARGS_W, w_res: W_Object) ->None:
        args_key = tuple(w_arg.spy_key(self.vm) for w_arg in args_w)
        key = (w_func, args_key)
        self.data[key] = w_res
        if DEBUG:
            self._debug('record', w_func, args_key, w_res)

    def lookup(self, w_func: W_Func, args_w: ARGS_W) -> Optional[W_Object]:
        args_key = tuple(w_arg.spy_key(self.vm) for w_arg in args_w)
        key = (w_func, args_key)
        w_res = self.data.get(key)
        if DEBUG:
            self._debug('lookup', w_func, args_key, w_res)
        return w_res

    def _debug(
        self,
        what: str,
        w_func: W_Func,
        args_key: ARGS_KEY,
        w_res: W_Object
    ) -> None:
        args_key = [self._fmt_key(k) for k in args_key]
        args = ', '.join(args_key)

        if what == 'lookup' and w_res is not None:
            what = Color.set('green', what)
        elif what == 'record':
            what = Color.set('teal', what)

        print(f'BlueCache.{what}: {w_func.fqn} {args} -> {w_res}')

    def _fmt_key(self, k: Any, keycolor: Optional[str]=None) -> str:
        if isinstance(k, tuple) and len(k) == 4 and k[0] == 'OpArg':
            # this is a key coming from W_OpArg: it's common enough which
            # is worth special casing its formatting for readability
            # purposes
            _, color, t, val = k
            k = f"OpArg('{color}', {t.fqn}, {val})"
            return Color.set(color, str(k))
        else:
            return str(k)

    def pp(self, funcname: Optional[str] = None) -> None:
        if funcname is None:
            self._pp_summary()
        else:
            self._pp_func(funcname)

    def _pp_summary(self) -> None:
        c: Counter[W_Func] = Counter()
        for (w_func, args_key), w_result in self.data.items():
            c[w_func] += 1
        print()
        print('=== vm.bluecache ===')
        print('Entries | Function')
        for w_func, n in c.most_common():
            print(f'{n:7d} | {w_func.fqn}')

    def _pp_func(self, funcname: str) -> None:
        for key, w_result in self.data.items():
            w_func, args_key = key
            if funcname in str(w_func.fqn):
                print(w_func.fqn)
                for arg in args_key:
                    print('   ', arg)
                print('    ==>')
                print('   ', w_result)
                print()
