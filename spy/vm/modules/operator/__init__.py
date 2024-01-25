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
"""

from spy.vm.function import W_Func
from spy.vm.registry import ModuleRegistry

class OperatorRegistry(ModuleRegistry):
    """
    Like ModuleRegistry, but adds a from_token method.
    """

    _from_token: dict[str, W_Func] = {}
    def from_token(self, token: str) -> W_Func:
        """
        Return the generic operator corresponding to the given token.

        E.g., OPS.from_token('+') returns OPS.w_ADD.
        """
        return self._from_token[token]

    def to_token(self, w_OP: W_Func) -> str:
        """
        Inverse of from_token
        """
        for token, w_obj in self._from_token.items():
            if w_obj is w_OP:
                return token
        raise KeyError(w_OP)


OPERATOR = OperatorRegistry('operator', '<operator>')
OP = OPERATOR

# the folloing imports register all the various objects on OP
from . import opimpl_i32     # side effects
from . import opimpl_str     # side effects
from . import opimpl_dynamic # side effects
from . import binop          # side effects


# fill the _from_token dict
OP._from_token.update({
    '+': OP.w_ADD,
    '*': OP.w_MUL,
    '==': OP.w_EQ,
    '!=': OP.w_NE,
    '<':  OP.w_LT,
    '<=': OP.w_LE,
    '>':  OP.w_GT,
    '>=': OP.w_GE,
    '[]': OP.w_GETITEM,
})
