from spy.vm.function import W_Func
from spy.vm.registry import ModuleRegistry

OPS = ModuleRegistry('builtins.ops', '<builtins.ops>')

def OP_from_token(op: str) -> W_Func:
    """
    Return the generic operator corresponding to the given symbol.

    E.g., by_op('+') returns ops.ADD.
    """
    d = {
        '+': OPS.w_ADD,
        '*': OPS.w_MUL,
        '==': OPS.w_EQ,
        '!=': OPS.w_NE,
        '<':  OPS.w_LT,
        '<=': OPS.w_LE,
        '>':  OPS.w_GT,
        '>=': OPS.w_GE,
        '[]': OPS.w_GETITEM,
    }
    return d[op]


from . import opimpl_i32 # side effects
from . import opimpl_str # side effects
from . import binop      # side effects
