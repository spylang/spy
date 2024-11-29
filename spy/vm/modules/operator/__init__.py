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

from spy.vm.function import W_Func
from spy.vm.b import OPERATOR, OP

# the folloing imports register all the various objects on OP
from . import opimpl_i32     # side effects
from . import opimpl_f64     # side effects
from . import opimpl_str     # side effects
from . import opimpl_object  # side effects
from . import opimpl_dynamic # side effects
from . import binop          # side effects
from . import attrop         # side effects
from . import itemop         # side effects
from . import callop         # side effects
from . import convop         # side effects


_from_token: dict[str, W_Func] = {
    '+': OP.w_ADD,
    '-': OP.w_SUB,
    '*': OP.w_MUL,
    '/': OP.w_DIV,
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

def OP_from_token(token: str) -> W_Func:
    """
    Return the generic operator corresponding to the given token.

    E.g., OPS.from_token('+') returns OPS.w_ADD.
    """
    return _from_token[token]
