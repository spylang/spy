from spy.location import Loc
from spy.vm.opspec import W_OpArg
from spy.vm.vm import SPyVM
from spy.vm.b import B

def test_oparg_eq():
    def eq(w_a, w_b):
        w_res = vm.universal_eq(w_a, w_b)
        return vm.unwrap(w_res)

    vm = SPyVM()

    # red OpArgs are equals if the w_T is equal
    wop_r1 = W_OpArg(vm, 'red', B.w_i32, None, Loc.fake())
    wop_r2 = W_OpArg(vm, 'red', B.w_i32, None, Loc.fake())
    wop_r3 = W_OpArg(vm, 'red', B.w_f64, None, Loc.fake())
    #assert eq(wop_r1, wop_r2)      # same T
    #assert not eq(wop_r1, wop_r3)  # different T

    # blue OpArgs are equals is the both w_T and w_blueval is equal
    wop_b1 = W_OpArg(vm, 'blue', B.w_i32, vm.wrap(42), Loc.fake())
    wop_b2 = W_OpArg(vm, 'blue', B.w_i32, vm.wrap(42), Loc.fake())
    wop_b3 = W_OpArg(vm, 'blue', B.w_i32, vm.wrap(43), Loc.fake())
    wop_b4 = W_OpArg(vm, 'blue', B.w_f64, vm.wrap(42.0), Loc.fake())

    #assert eq(wop_b1, wop_b2)      # same T, same blueval
    assert not eq(wop_b1, wop_b3)  # same T, different bluevale
    #assert not eq(wop_b1, wop_b4)  # different T

def test_oparg_key():
    vm = SPyVM()
    w_a = vm.wrap('x')
    w_b = vm.wrap('x')
    wop_a = W_OpArg.from_w_obj(vm, w_a)
    wop_b = W_OpArg.from_w_obj(vm, w_b)
    assert wop_a.spy_key(vm) == wop_b.spy_key(vm)
