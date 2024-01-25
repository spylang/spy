from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type
from . import OPS
from .multimethod import MultiMethodTable
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

MM = MultiMethodTable()

MM.register('==', 'i32', 'i32', OPS.w_i32_eq)
MM.register('!=', 'i32', 'i32', OPS.w_i32_ne)
MM.register('<' , 'i32', 'i32', OPS.w_i32_lt)
MM.register('<=', 'i32', 'i32', OPS.w_i32_le)
MM.register('>' , 'i32', 'i32', OPS.w_i32_gt)
MM.register('>=', 'i32', 'i32', OPS.w_i32_ge)

# XXX these should be labeled as 'blue'
@OPS.primitive('def(l: type, r: type) -> dynamic')
def ADD(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_Object:
    if w_ltype is w_rtype is B.w_i32:
        return OPS.w_i32_add
    elif w_ltype is w_rtype is B.w_str:
        return OPS.w_str_add
    return B.w_NotImplemented

@OPS.primitive('def(l: type, r: type) -> dynamic')
def MUL(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_Object:
    if w_ltype is w_rtype is B.w_i32:
        return OPS.w_i32_mul
    if w_ltype is B.w_str and w_rtype is B.w_i32:
        return OPS.w_str_mul
    return B.w_NotImplemented

@OPS.primitive('def(l: type, r: type) -> dynamic')
def GETITEM(vm: 'SPyVM', w_vtype: W_Type, w_itype: W_Type) -> W_Object:
    if w_vtype is B.w_str and w_itype is B.w_i32:
        return OPS.w_str_getitem
    return B.w_NotImplemented


@OPS.primitive('def(l: type, r: type) -> dynamic')
def EQ(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_Object:
    return MM.lookup('==', w_ltype, w_rtype)

@OPS.primitive('def(l: type, r: type) -> dynamic')
def NE(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_Object:
    return MM.lookup('!=', w_ltype, w_rtype)

@OPS.primitive('def(l: type, r: type) -> dynamic')
def LT(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_Object:
    return MM.lookup('<', w_ltype, w_rtype)

@OPS.primitive('def(l: type, r: type) -> dynamic')
def LE(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_Object:
    return MM.lookup('<=', w_ltype, w_rtype)

@OPS.primitive('def(l: type, r: type) -> dynamic')
def GT(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_Object:
    return MM.lookup('>', w_ltype, w_rtype)

@OPS.primitive('def(l: type, r: type) -> dynamic')
def GE(vm: 'SPyVM', w_ltype: W_Type, w_rtype: W_Type) -> W_Object:
    return MM.lookup('>=', w_ltype, w_rtype)
