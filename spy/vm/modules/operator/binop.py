from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.object import W_Dynamic, W_Type
from spy.vm.opimpl import W_OpImpl
from . import OP
from .multimethod import MultiMethodTable
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

MM = MultiMethodTable()

# i32 ops
MM.register('+',  'i32', 'i32', OP.w_i32_add)
MM.register('-',  'i32', 'i32', OP.w_i32_sub)
MM.register('*',  'i32', 'i32', OP.w_i32_mul)
MM.register('/',  'i32', 'i32', OP.w_i32_div)
MM.register('==', 'i32', 'i32', OP.w_i32_eq)
MM.register('!=', 'i32', 'i32', OP.w_i32_ne)
MM.register('<' , 'i32', 'i32', OP.w_i32_lt)
MM.register('<=', 'i32', 'i32', OP.w_i32_le)
MM.register('>' , 'i32', 'i32', OP.w_i32_gt)
MM.register('>=', 'i32', 'i32', OP.w_i32_ge)

# f64 ops
MM.register('+',  'f64', 'f64', OP.w_f64_add)
MM.register('-',  'f64', 'f64', OP.w_f64_sub)
MM.register('*',  'f64', 'f64', OP.w_f64_mul)
MM.register('/',  'f64', 'f64', OP.w_f64_div)
MM.register('==', 'f64', 'f64', OP.w_f64_eq)
MM.register('!=', 'f64', 'f64', OP.w_f64_ne)
MM.register('<' , 'f64', 'f64', OP.w_f64_lt)
MM.register('<=', 'f64', 'f64', OP.w_f64_le)
MM.register('>' , 'f64', 'f64', OP.w_f64_gt)
MM.register('>=', 'f64', 'f64', OP.w_f64_ge)

# mixed i32/f64 ops: this is still small enough that we can write it manually,
# but we should consider the idea of generating this table automatically. This
# will become especially relevant when we add more integer types.
MM.register('+',  'f64', 'i32', OP.w_f64_add)
MM.register('+',  'i32', 'f64', OP.w_f64_add)
MM.register('-',  'f64', 'i32', OP.w_f64_sub)
MM.register('-',  'i32', 'f64', OP.w_f64_sub)
MM.register('*',  'f64', 'i32', OP.w_f64_mul)
MM.register('*',  'i32', 'f64', OP.w_f64_mul)
MM.register('/',  'f64', 'i32', OP.w_f64_div)
MM.register('/',  'i32', 'f64', OP.w_f64_div)
MM.register('==', 'f64', 'i32', OP.w_f64_eq)
MM.register('==', 'i32', 'f64', OP.w_f64_eq)
MM.register('!=', 'f64', 'i32', OP.w_f64_ne)
MM.register('!=', 'i32', 'f64', OP.w_f64_ne)
MM.register('<' , 'f64', 'i32', OP.w_f64_lt)
MM.register('<' , 'i32', 'f64', OP.w_f64_lt)
MM.register('<=', 'f64', 'i32', OP.w_f64_le)
MM.register('<=', 'i32', 'f64', OP.w_f64_le)
MM.register('>' , 'f64', 'i32', OP.w_f64_gt)
MM.register('>' , 'i32', 'f64', OP.w_f64_gt)
MM.register('>=', 'f64', 'i32', OP.w_f64_ge)
MM.register('>=', 'i32', 'f64', OP.w_f64_ge)

# str ops
MM.register('+',  'str', 'str', OP.w_str_add)
MM.register('*',  'str', 'i32', OP.w_str_mul)
MM.register('==', 'str', 'str', OP.w_str_eq)
MM.register('!=', 'str', 'str', OP.w_str_ne)

# dynamic ops
MM.register_partial('+',  'dynamic', OP.w_dynamic_add)
MM.register_partial('*',  'dynamic', OP.w_dynamic_mul)
MM.register_partial('==', 'dynamic', OP.w_dynamic_eq)
MM.register_partial('!=', 'dynamic', OP.w_dynamic_ne)
MM.register_partial('<',  'dynamic', OP.w_dynamic_lt)
MM.register_partial('<=', 'dynamic', OP.w_dynamic_le)
MM.register_partial('>',  'dynamic', OP.w_dynamic_gt)
MM.register_partial('>=', 'dynamic', OP.w_dynamic_ge)


@OP.builtin(color='blue')
def ADD(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_OpImpl:
    return MM.lookup('+', w_ltype, w_rtype)

@OP.builtin(color='blue')
def SUB(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_OpImpl:
    return MM.lookup('-', w_ltype, w_rtype)

@OP.builtin(color='blue')
def MUL(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_OpImpl:
    return MM.lookup('*', w_ltype, w_rtype)

@OP.builtin(color='blue')
def DIV(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_OpImpl:
    return MM.lookup('/', w_ltype, w_rtype)

def can_use_reference_eq(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> bool:
    """
    We can use 'is' to implement 'eq' if:
      1. the two types have a common ancestor
      2. the common ancestor must be a reference type
    """
    w_common = vm.union_type(w_ltype, w_rtype)
    return w_common is not B.w_object and w_common.is_reference_type(vm)

@OP.builtin(color='blue')
def EQ(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_OpImpl:
    pyclass = w_ltype.pyclass
    if pyclass.has_meth_overriden('op_EQ'):
        return pyclass.op_EQ(vm, w_ltype, w_rtype)
    elif can_use_reference_eq(vm, w_ltype, w_rtype):
        return W_OpImpl(OP.w_object_is)
    else:
        return MM.lookup('==', w_ltype, w_rtype)

@OP.builtin(color='blue')
def NE(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_OpImpl:
    if can_use_reference_eq(vm, w_ltype, w_rtype):
        return W_OpImpl(OP.w_object_isnot)
    return MM.lookup('!=', w_ltype, w_rtype)

@OP.builtin(color='blue')
def UNIVERSAL_EQ(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_OpImpl:
    return W_OpImpl(OP.w_object_universal_eq)

@OP.builtin(color='blue')
def UNIVERSAL_NE(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_OpImpl:
    return W_OpImpl(OP.w_object_universal_ne)

@OP.builtin(color='blue')
def LT(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_OpImpl:
    return MM.lookup('<', w_ltype, w_rtype)

@OP.builtin(color='blue')
def LE(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_OpImpl:
    return MM.lookup('<=', w_ltype, w_rtype)

@OP.builtin(color='blue')
def GT(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_OpImpl:
    return MM.lookup('>', w_ltype, w_rtype)

@OP.builtin(color='blue')
def GE(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_OpImpl:
    return MM.lookup('>=', w_ltype, w_rtype)
