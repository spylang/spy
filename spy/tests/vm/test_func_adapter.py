import pytest
from spy.vm.vm import SPyVM
from spy.vm.function import W_FuncType
from spy.vm.func_adapter import W_FuncAdapter, ArgSpec
from spy.vm.primitive import W_I32
from spy.vm.str import W_Str
from spy.vm.builtin import builtin_func
from spy.vm.b import OP


@builtin_func('test')
def w_repeat(vm: 'SPyVM', w_s: W_Str, w_n: W_I32) -> W_Str:
    s = vm.unwrap_str(w_s)
    n = vm.unwrap_i32(w_n)
    return vm.wrap(s * int(n))  # type: ignore

def test_repeat():
    vm = SPyVM()
    w_s = vm.call(w_repeat, [vm.wrap('ab '), vm.wrap(3)])
    assert vm.unwrap_str(w_s) == 'ab ab ab '

def test_shuffle_args():
    vm = SPyVM()
    w_functype = W_FuncType.parse('def(n: i32, s: str) -> str')
    w_adapter = W_FuncAdapter(
        w_functype,
        w_repeat,
        [ArgSpec.Arg(1), ArgSpec.Arg(0)]
    )
    w_s = vm.call(w_adapter, [vm.wrap(3), vm.wrap('ab ')])
    assert vm.unwrap_str(w_s) == 'ab ab ab '

def test_const():
    vm = SPyVM()
    w_functype = W_FuncType.parse('def(n: i32) -> str')
    w_s = vm.wrap('ab ')
    w_adapter = W_FuncAdapter(
        w_functype,
        w_repeat,
        [ArgSpec.Const(w_s), ArgSpec.Arg(0)]
    )
    w_s = vm.call(w_adapter, [vm.wrap(3)])
    assert vm.unwrap_str(w_s) == 'ab ab ab '

def test_converter():
    vm = SPyVM()
    w_functype = W_FuncType.parse('def(x: f64, s: str) -> str')
    w_adapter = W_FuncAdapter(
        w_functype,
        w_repeat,
        [ArgSpec.Arg(1), ArgSpec.Arg(0, OP.w_f64_to_i32)]
    )
    w_s = vm.call(w_adapter, [vm.wrap(3.5), vm.wrap('ab ')])
    assert vm.unwrap_str(w_s) == 'ab ab ab '
