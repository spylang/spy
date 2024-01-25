from typing import TYPE_CHECKING, Any, Optional
from spy.vm.b import B
from spy.vm.str import W_str
from spy.vm.object import W_Object, W_Type, W_i32, W_bool
from spy.vm.function import W_FuncType, W_Func
from spy.vm.registry import ModuleRegistry
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

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

# ================


from . import opimpl_i32 # side effects
from . import binop      # side effects



# ==================

@OPS.primitive('def(a: str, b: str) -> str')
def str_add(vm: 'SPyVM', w_a: W_str, w_b: W_str) -> W_str:
    assert isinstance(w_a, W_str)
    assert isinstance(w_b, W_str)
    ptr_c = vm.ll.call('spy_str_add', w_a.ptr, w_b.ptr)
    return W_str.from_ptr(vm, ptr_c)

@OPS.primitive('def(s: str, n: i32) -> str')
def str_mul(vm: 'SPyVM', w_a: W_str, w_b: W_i32) -> W_str:
    assert isinstance(w_a, W_str)
    assert isinstance(w_b, W_i32)
    ptr_c = vm.ll.call('spy_str_mul', w_a.ptr, w_b.value)
    return W_str.from_ptr(vm, ptr_c)

@OPS.primitive('def(s: str, i: i32) -> str')
def str_getitem(vm: 'SPyVM', w_s: W_str, w_i: W_i32) -> W_str:
    assert isinstance(w_s, W_str)
    assert isinstance(w_i, W_i32)
    ptr_c = vm.ll.call('spy_str_getitem', w_s.ptr, w_i.value)
    return W_str.from_ptr(vm, ptr_c)
