from spy.location import Loc
from spy.vm.opspec import W_MetaArg
from spy.vm.vm import SPyVM
from spy.vm.b import B
from spy.vm.object import W_Object

def test_oparg_eq():
    def eq(w_a: W_Object, w_b: W_Object) -> bool:
        w_res = vm.universal_eq(w_a, w_b)
        return vm.unwrap(w_res)

    vm = SPyVM()

    # red OpArgs are equals if the w_T is equal
    wm_r1 = W_MetaArg(vm, 'red', B.w_i32, None, Loc.fake())
    wm_r2 = W_MetaArg(vm, 'red', B.w_i32, None, Loc.fake())
    wm_r3 = W_MetaArg(vm, 'red', B.w_f64, None, Loc.fake())
    assert eq(wm_r1, wm_r2)      # same T
    assert not eq(wm_r1, wm_r3)  # different T

    # blue OpArgs are equals is the both w_T and w_blueval is equal
    wm_b1 = W_MetaArg(vm, 'blue', B.w_i32, vm.wrap(42), Loc.fake())
    wm_b2 = W_MetaArg(vm, 'blue', B.w_i32, vm.wrap(42), Loc.fake())
    wm_b3 = W_MetaArg(vm, 'blue', B.w_i32, vm.wrap(43), Loc.fake())
    wm_b4 = W_MetaArg(vm, 'blue', B.w_f64, vm.wrap(42.0), Loc.fake())

    assert eq(wm_b1, wm_b2)      # same T, same blueval
    assert not eq(wm_b1, wm_b3)  # same T, different bluevale
    assert not eq(wm_b1, wm_b4)  # different T

def test_oparg_key():
    vm = SPyVM()
    w_a = vm.wrap('x')
    w_b = vm.wrap('x')
    wm_a = W_MetaArg.from_w_obj(vm, w_a)
    wm_b = W_MetaArg.from_w_obj(vm, w_b)
    assert wm_a.spy_key(vm) == wm_b.spy_key(vm)
