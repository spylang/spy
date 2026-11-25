"""
PROTOTYPE tests for calling prebuilt (compiled) stdlib functions from the
interpreter. See spy.vm.native and spy.build.native_stdlib.
"""

import pytest

from spy.errors import SPyError
from spy.fqn import FQN
from spy.vm.function import W_Func
from spy.vm.native import W_NativeCell, W_NativeFunc
from spy.vm.object import W_Object
from spy.vm.primitive import W_F64, W_U32
from spy.vm.vm import SPyVM

REF_42 = [
    0.3745401188473625,
    0.9507143064099162,
    0.7319939418114051,
    0.5986584841970366,
    0.15601864044243652,
]


def make_vm(native: bool) -> SPyVM:
    vm = SPyVM(native_stdlib=native)
    vm.import_("random")
    return vm


def call(vm: SPyVM, name: str, *args: W_Object) -> W_Object:
    w_func = vm.lookup_global(FQN(name))
    assert isinstance(w_func, W_Func)
    return vm.fast_call(w_func, list(args))


@pytest.fixture(scope="module")
def nvm() -> SPyVM:
    return make_vm(native=True)


class TestNativeStdlib:
    def test_functions_are_replaced(self, nvm):
        assert isinstance(nvm.lookup_global(FQN("random::seed")), W_NativeFunc)
        assert isinstance(nvm.lookup_global(FQN("random::random")), W_NativeFunc)
        # functions of other modules which are not in the manifest stay
        # interpreted
        w_func = nvm.lookup_global(FQN("_random::_get_global_random"))
        assert not isinstance(w_func, W_NativeFunc)

    def test_module_var_is_native_cell(self, nvm):
        w_cell = nvm.lookup_global(FQN("_random::_ptr_global_random"))
        assert isinstance(w_cell, W_NativeCell)

    def test_values(self, nvm):
        call(nvm, "random::seed", W_U32(42))
        got = [nvm.unwrap(call(nvm, "random::random")) for _ in range(5)]
        assert got == REF_42

    def test_u32_above_i32_max(self, nvm):
        # u32 args >= 2**31 must survive the trip through wasm's signed i32
        call(nvm, "random::seed", W_U32(2**32 - 1))
        x = nvm.unwrap(call(nvm, "random::random"))
        assert 0.0 <= x < 1.0

    def test_uniform(self, nvm):
        call(nvm, "random::seed", W_U32(42))
        x = nvm.unwrap(call(nvm, "random::uniform", W_F64(10.0), W_F64(20.0)))
        assert x == pytest.approx(10.0 + REF_42[0] * 10.0)

    def test_error_path(self, nvm):
        # the compiled code calls spy_operator$raise: it must surface as a
        # normal SPyError in the interpreter
        with pytest.raises(SPyError) as exc:
            call(nvm, "random::uniform", W_F64(2.0), W_F64(1.0))
        assert exc.value.etype == "W_ValueError"
        assert "a must be <= b" in exc.value.format(use_colors=False)

    def test_vm_still_usable_after_error(self, nvm):
        with pytest.raises(SPyError):
            call(nvm, "random::uniform", W_F64(2.0), W_F64(1.0))
        call(nvm, "random::seed", W_U32(42))
        assert nvm.unwrap(call(nvm, "random::random")) == REF_42[0]

    def test_interp_sees_state_written_by_native_code(self, nvm):
        # seed natively, then draw using the INTERPRETED Random.random().
        # This checks that (1) the cell redirect points to the C global and
        # (2) the interp's view of the struct layout in memory matches the
        # one used by the compiled code.
        call(nvm, "random::seed", W_U32(42))
        w_rnd = call(nvm, "_random::_get_global_random", W_U32(0), nvm.wrap(False))
        w_x = call(nvm, "_random::Random::random", w_rnd)
        assert nvm.unwrap(w_x) == REF_42[0]
        # and the compiled code continues the same stream
        assert nvm.unwrap(call(nvm, "random::random")) == REF_42[1]

    def test_native_sees_state_written_by_interp(self, nvm):
        # reseed via the INTERPRETED _get_global_random(reset=True), then
        # draw natively. Compare against a fully interpreted VM.
        w_seed = W_U32(7)
        call(nvm, "_random::_get_global_random", w_seed, nvm.wrap(True))
        got = nvm.unwrap(call(nvm, "random::random"))

        ivm = make_vm(native=False)
        call(ivm, "random::seed", W_U32(7))
        expected = ivm.unwrap(call(ivm, "random::random"))
        assert got == expected
