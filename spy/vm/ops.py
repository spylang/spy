from typing import TYPE_CHECKING, Any, Optional
from spy.vm.builtins import B
from spy.vm.str import W_str
from spy.vm.object import W_Object, W_Type, W_i32
from spy.vm.function import W_FuncType
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

def get(funcname: str) -> Any:
    func = globals().get(funcname)
    if func is None:
        raise KeyError(f'Cannot find {funcname} in spy/vm/ops.py')
    return func

def signature(sig: str) -> Any:
    w_functype = W_FuncType.parse(sig)
    def decorator(fn: Any) -> Any:
        fn.w_functype = w_functype
        fn.spy_opname = fn.__name__
        return fn
    return decorator

# ================

# XXX explain me

def ADD(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> Any:
    if w_ltype is w_rtype is B.w_i32:
        return i32_add
    elif w_ltype is w_rtype is B.w_str:
        return str_add
    return None

def MUL(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> Any:
    if w_ltype is w_rtype is B.w_i32:
        return i32_mul
    if w_ltype is B.w_str and w_rtype is B.w_i32:
        return str_mul
    return None

def GETITEM(vm: 'SPyVM', w_vtype: W_Type, w_itype: W_Type) -> Any:
    if w_vtype is B.w_str and w_itype is B.w_i32:
        return str_getitem
    return None


@signature('def(a: i32, b: i32) -> i32')
def i32_add(vm: 'SPyVM', w_a: W_i32, w_b: W_i32) -> W_i32:
    a = vm.unwrap(w_a)
    b = vm.unwrap(w_b)
    return vm.wrap(a + b) # type: ignore


@signature('def(a: i32, b: i32) -> i32')
def i32_mul(vm: 'SPyVM', w_a: W_i32, w_b: W_i32) -> W_i32:
    a = vm.unwrap(w_a)
    b = vm.unwrap(w_b)
    return vm.wrap(a * b) # type: ignore


# ==================

@signature('def(a: str, b: str) -> str')
def str_add(vm: 'SPyVM', w_a: W_str, w_b: W_str) -> W_str:
    assert isinstance(w_a, W_str)
    assert isinstance(w_b, W_str)
    ptr_c = vm.ll.call('spy_str_add', w_a.ptr, w_b.ptr)
    return W_str.from_ptr(vm, ptr_c)

@signature('def(s: str, n: i32) -> str')
def str_mul(vm: 'SPyVM', w_a: W_str, w_b: W_i32) -> W_str:
    assert isinstance(w_a, W_str)
    assert isinstance(w_b, W_i32)
    ptr_c = vm.ll.call('spy_str_mul', w_a.ptr, w_b.value)
    return W_str.from_ptr(vm, ptr_c)

@signature('def(s: str, i: i32) -> str')
def str_getitem(vm: 'SPyVM', w_s: W_str, w_i: W_i32) -> W_str:
    assert isinstance(w_s, W_str)
    assert isinstance(w_i, W_i32)
    ptr_c = vm.ll.call('spy_str_getitem', w_s.ptr, w_i.value)
    return W_str.from_ptr(vm, ptr_c)
