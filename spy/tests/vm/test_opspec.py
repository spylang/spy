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

    # red MetaArgs are equals if the w_T is equal
    wam_r1 = W_MetaArg(vm, "red", B.w_i32, None, Loc.fake())
    wam_r2 = W_MetaArg(vm, "red", B.w_i32, None, Loc.fake())
    wam_r3 = W_MetaArg(vm, "red", B.w_f64, None, Loc.fake())
    assert eq(wam_r1, wam_r2)      # same T
    assert not eq(wam_r1, wam_r3)  # different T

    # blue MetaArgs are equals is the both w_T and w_blueval is equal
    wam_b1 = W_MetaArg(vm, "blue", B.w_i32, vm.wrap(42), Loc.fake())
    wam_b2 = W_MetaArg(vm, "blue", B.w_i32, vm.wrap(42), Loc.fake())
    wam_b3 = W_MetaArg(vm, "blue", B.w_i32, vm.wrap(43), Loc.fake())
    wam_b4 = W_MetaArg(vm, "blue", B.w_f64, vm.wrap(42.0), Loc.fake())

    assert eq(wam_b1, wam_b2)      # same T, same blueval
    assert not eq(wam_b1, wam_b3)  # same T, different bluevale
    assert not eq(wam_b1, wam_b4)  # different T

def test_oparg_key():
    vm = SPyVM()
    w_a = vm.wrap("x")
    w_b = vm.wrap("x")
    wam_a = W_MetaArg.from_w_obj(vm, w_a)
    wam_b = W_MetaArg.from_w_obj(vm, w_b)
    assert wam_a.spy_key(vm) == wam_b.spy_key(vm)
