from typing import TYPE_CHECKING, Any, Optional
from spy.vm.builtins import B
from spy.vm.str import W_str
from spy.vm.object import W_Object, W_Type, W_i32
from spy.vm.function import W_FuncType, W_Func
from spy.vm.registry import ModuleRegistry
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

def get(funcname: str) -> Any:
    func = globals().get(funcname)
    if func is None:
        raise KeyError(f'Cannot find {funcname} in spy/vm/ops.py')
    return func

OPS = ModuleRegistry('__ops__', '<__ops__>')

# ================

# XXX explain me

def ADD(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_Func:
    if w_ltype is w_rtype is B.w_i32:
        return OPS.w_i32_add
    elif w_ltype is w_rtype is B.w_str:
        return OPS.w_str_add
    return None

def MUL(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_Func:
    if w_ltype is w_rtype is B.w_i32:
        return OPS.w_i32_mul
    if w_ltype is B.w_str and w_rtype is B.w_i32:
        return OPW.w_str_mul
    return None

def GETITEM(vm: 'SPyVM', w_vtype: W_Type, w_itype: W_Type) -> W_Func:
    if w_vtype is B.w_str and w_itype is B.w_i32:
        return OPW.w_str_getitem
    return None


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
