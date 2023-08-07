"""
Multiple dispatch for compiler operations.

Every MultiOp instance represent an operation which can be emitted by the
compiler (e.g. BinaryAdd, GetItem, etc.).

Every MultiOp can have one or more registered implementation, one for each
combination of w_types.
"""
from typing import Union, Any, Optional
from dataclasses import dataclass
from spy.vm.object import W_Type

Key = tuple[W_Type, ...]

@dataclass
class OpImpl:
    name: str
    types_w: tuple[W_Type, ...]
    w_restype: W_Type
    emit: Any


class MultiOp:
    name: str
    nargs: int
    impls: dict[Key, OpImpl]

    def __init__(self, name: str, nargs: int):
        self.name = name
        self.nargs = nargs
        self.impls = {}

    def __call__(self, *types_w: W_Type, w_restype: W_Type) -> Any:
        got = len(types_w)
        exp = self.nargs
        if got != exp:
            raise TypeError(f'Wrong number of arguments: expected {exp}, got {got}')

        def decorator(fn: Any) -> Any:
            if types_w in self.impls:
                raise ValueError('already registered')
            self.impls[types_w] = OpImpl(self.name, types_w, w_restype, fn)
            return fn
        return decorator

    def lookup(self, *types_w: W_Type) -> Optional[OpImpl]:
        # eventually we need a proper multi-dispatch mechanism with
        # promotions, but for now this should work good enough
        return self.impls.get(types_w)


# standard multiop
GetItem: MultiOp = MultiOp('GetItem', 2)

# implort the various op*.py files, to register all MultiOp
# implementations. All these imports have side effects.
from spy.irgen import ops
