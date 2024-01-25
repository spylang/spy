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


OPS = OperatorRegistry('builtins.ops', '<builtins.ops>')

# the folloing imports register all the various objects on OPS
from . import opimpl_i32 # side effects
from . import opimpl_str # side effects
from . import binop      # side effects


# fill the _from_token dict
OPS._from_token.update({
    '+': OPS.w_ADD,
    '*': OPS.w_MUL,
    '==': OPS.w_EQ,
    '!=': OPS.w_NE,
    '<':  OPS.w_LT,
    '<=': OPS.w_LE,
    '>':  OPS.w_GT,
    '>=': OPS.w_GE,
    '[]': OPS.w_GETITEM,
})
