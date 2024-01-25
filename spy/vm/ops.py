from typing import TYPE_CHECKING, Any, Optional
from spy.vm.b import B
from spy.vm.str import W_str
from spy.vm.object import W_Object, W_Type, W_i32, W_bool
from spy.vm.function import W_FuncType, W_Func
from spy.vm.registry import ModuleRegistry
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

OPS = ModuleRegistry('builtins.ops', '<builtins.ops>')

def by_op(op: str) -> Any:
    """
    Return the generic operator corresponding to the given symbol.

    E.g., by_op('+') returns ops.ADD.
    """
    d = {
        '+': ADD,
        '*': MUL,
        '==': EQ,
        '!=': NE,
        '<':  LT,
        '<=': LE,
        '>':  GT,
        '>=': GE,
        '[]': GETITEM,
    }
    return d[op]

# ================

# XXX explain me

def ADD(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_Object:
    if w_ltype is w_rtype is B.w_i32:
        return OPS.w_i32_add
    elif w_ltype is w_rtype is B.w_str:
        return OPS.w_str_add
    return B.w_NotImplemented

def MUL(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_Object:
    if w_ltype is w_rtype is B.w_i32:
        return OPS.w_i32_mul
    if w_ltype is B.w_str and w_rtype is B.w_i32:
        return OPS.w_str_mul
    return B.w_NotImplemented

def GETITEM(vm: 'SPyVM', w_vtype: W_Type, w_itype: W_Type) -> W_Object:
    if w_vtype is B.w_str and w_itype is B.w_i32:
        return OPS.w_str_getitem
    return B.w_NotImplemented


@OPS.primitive('def(a: i32, b: i32) -> i32')
def i32_add(vm: 'SPyVM', w_a: W_i32, w_b: W_i32) -> W_i32:
    a = vm.unwrap(w_a)
    b = vm.unwrap(w_b)
    return vm.wrap(a + b) # type: ignore


@OPS.primitive('def(a: i32, b: i32) -> i32')
def i32_mul(vm: 'SPyVM', w_a: W_i32, w_b: W_i32) -> W_i32:
    a = vm.unwrap(w_a)
    b = vm.unwrap(w_b)
    return vm.wrap(a * b) # type: ignore

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


# ==================
# comparison ops

# the following style is way too verbose. We could greatly reduce code
# duplication by using some metaprogramming, but it might become too
# magic. Let's to the dumb&verbose thing for now

def _generic_i32_op(vm: 'SPyVM', w_a: W_Object, w_b: W_Object, fn: Any) -> Any:
    a = vm.unwrap(w_a)
    b = vm.unwrap(w_b)
    res = fn(a, b)
    return vm.wrap(res)

@OPS.primitive('def(a: i32, b: i32) -> bool')
def i32_eq(vm: 'SPyVM', w_a: W_i32, w_b: W_i32) -> W_bool:
    return _generic_i32_op(vm, w_a, w_b, lambda a, b: a == b)

@OPS.primitive('def(a: i32, b: i32) -> bool')
def i32_ne(vm: 'SPyVM', w_a: W_i32, w_b: W_i32) -> W_bool:
    return _generic_i32_op(vm, w_a, w_b, lambda a, b: a != b)

@OPS.primitive('def(a: i32, b: i32) -> bool')
def i32_lt(vm: 'SPyVM', w_a: W_i32, w_b: W_i32) -> W_bool:
    return _generic_i32_op(vm, w_a, w_b, lambda a, b: a < b)

@OPS.primitive('def(a: i32, b: i32) -> bool')
def i32_le(vm: 'SPyVM', w_a: W_i32, w_b: W_i32) -> W_bool:
    return _generic_i32_op(vm, w_a, w_b, lambda a, b: a <= b)

@OPS.primitive('def(a: i32, b: i32) -> bool')
def i32_gt(vm: 'SPyVM', w_a: W_i32, w_b: W_i32) -> W_bool:
    return _generic_i32_op(vm, w_a, w_b, lambda a, b: a > b)

@OPS.primitive('def(a: i32, b: i32) -> bool')
def i32_ge(vm: 'SPyVM', w_a: W_i32, w_b: W_i32) -> W_bool:
    return _generic_i32_op(vm, w_a, w_b, lambda a, b: a >= b)

CMPOPS = {
    (B.w_i32, B.w_i32, '=='): OPS.w_i32_eq,
    (B.w_i32, B.w_i32, '!='): OPS.w_i32_ne,
    (B.w_i32, B.w_i32, '<' ): OPS.w_i32_lt,
    (B.w_i32, B.w_i32, '<='): OPS.w_i32_le,
    (B.w_i32, B.w_i32, '>' ): OPS.w_i32_gt,
    (B.w_i32, B.w_i32, '>='): OPS.w_i32_ge,
}

def EQ(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_Object:
    key = (w_ltype, w_rtype, '==')
    return CMPOPS.get(key, B.w_NotImplemented)

def NE(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_Object:
    key = (w_ltype, w_rtype, '!=')
    return CMPOPS.get(key, B.w_NotImplemented)

def LT(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_Object:
    key = (w_ltype, w_rtype, '<')
    return CMPOPS.get(key, B.w_NotImplemented)

def LE(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_Object:
    key = (w_ltype, w_rtype, '<=')
    return CMPOPS.get(key, B.w_NotImplemented)

def GT(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_Object:
    key = (w_ltype, w_rtype, '>')
    return CMPOPS.get(key, B.w_NotImplemented)

def GE(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_Object:
    key = (w_ltype, w_rtype, '>=')
    return CMPOPS.get(key, B.w_NotImplemented)
