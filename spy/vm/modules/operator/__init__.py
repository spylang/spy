"""
SPy `operator` module.

This is a central piece of how SPy works. First, some lexicon:

  - "generic operator", also known as "operator": a blue function which takes
    two types and return an opimpl

  - "opimpl": a red function which takes two operands and return the result

Basically, this means that the following code:

    c = a + b

Is roughly equivalent to this:

    Ta = STATIC_TYPE(a)
    Tb = STATIC_TYPE(b)
    c = operator.ADD(Ta, Tb)(a, b)

The dispatch ALWAYS happens on the static types of operands. So for example,
if you have the following code:

    a: object = 1
    b: object = 2
    a + b

It's a SPyTypeError, because we don't have an opimpl for "object + object".

The exception is the type `dynamic`:

    a: dynamic = 1
    b: dynamic = 2
    a + b

In this case, the dispatch will be done on the dynamic type of the operands.

Note that for bootstrap reason, the OPERATOR module is defined in vm/b.py, and
re-exported here.
"""

from typing import TYPE_CHECKING, Sequence
from spy.errors import WIP
from spy.vm.object import W_Object
from spy.vm.function import W_Func
from spy.vm.opspec import W_OpSpec, W_OpArg
from spy.vm.b import OPERATOR, OP

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


# the folloing imports register all the various objects on OP
from . import opimpl_int     # noqa: F401 -- side effects
from . import opimpl_f64     # noqa: F401 -- side effects
from . import opimpl_str     # noqa: F401 -- side effects
from . import opimpl_object  # noqa: F401 -- side effects
from . import opimpl_dynamic # noqa: F401 -- side effects
from . import opimpl_bool    # noqa: F401 -- side effects
from . import unaryop        # noqa: F401 -- side effects
from . import binop          # noqa: F401 -- side effects
from . import attrop         # noqa: F401 -- side effects
from . import itemop         # noqa: F401 -- side effects
from . import callop         # noqa: F401 -- side effects
from . import convop         # noqa: F401 -- side effects
from . import raiseop        # noqa: F401 -- side effects

_from_token: dict[str, W_Func] = {
    '+': OP.w_ADD,
    '-': OP.w_SUB,
    '*': OP.w_MUL,
    '/': OP.w_DIV,
    '//': OP.w_FLOORDIV,
    '%': OP.w_MOD,
    '<<': OP.w_LSHIFT,
    '>>': OP.w_RSHIFT,
    '&': OP.w_AND,
    '|': OP.w_OR,
    '^': OP.w_XOR,
    '==': OP.w_EQ,
    '!=': OP.w_NE,
    '<':  OP.w_LT,
    '<=': OP.w_LE,
    '>':  OP.w_GT,
    '>=': OP.w_GE,
    '[]': OP.w_GETITEM,
    '<universal_eq>': OP.w_UNIVERSAL_EQ,
    '<universal_ne>': OP.w_UNIVERSAL_NE,
}

_unary_from_token: dict[str, W_Func] = {
    '-': OP.w_NEG,
}

def OP_from_token(token: str) -> W_Func:
    """
    Return the generic operator corresponding to the given token.

    E.g., OPS.from_token('+') returns OPS.w_ADD.
    """
    if token in _from_token:
        return _from_token[token]
    else:
        raise WIP(f"Operator not implemented yet: {token}")

def OP_unary_from_token(token: str) -> W_Func:
    return _unary_from_token[token]

def print_all_OPERATORS() -> None:
    """
    Just a development tool to print the list of all OPERATORs
    """
    print('SPy OPERATORS:')
    for fqn, w_func in OP.content:
        if fqn.symbol_name.isupper():
            print("   ", fqn)
    print()

#print_all_OPERATORS()
