import textwrap

from spy.location import Loc
from spy.vm.b import OP, B
from spy.vm.function import W_FuncType
from spy.vm.object import W_Object
from spy.vm.opimpl import ArgSpec, W_OpImpl
from spy.vm.primitive import W_I32
from spy.vm.str import W_Str
from spy.vm.vm import SPyVM


def make_w_repeat(vm: "SPyVM"):
    @vm.register_builtin_func("_testing_helpers")
    def w_repeat(vm: "SPyVM", w_s: W_Str, w_n: W_I32) -> W_Str:
        s = vm.unwrap_str(w_s)
        n = vm.unwrap_i32(w_n)
        return vm.wrap(s * int(n))

    return w_repeat


def test_repeat():
    vm = SPyVM()
    w_repeat = make_w_repeat(vm)
    w_s = vm.fast_call(w_repeat, [vm.wrap("ab "), vm.wrap(3)])
    assert vm.unwrap_str(w_s) == "ab ab ab "


def test_shuffle_args():
    vm = SPyVM()
    w_repeat = make_w_repeat(vm)
    w_functype = W_FuncType.parse("def(i32, str) -> str")
    w_opimpl = W_OpImpl(w_functype, w_repeat, [ArgSpec.Arg(1), ArgSpec.Arg(0)])
    w_s = w_opimpl._execute(vm, [vm.wrap(3), vm.wrap("ab ")])
    assert vm.unwrap_str(w_s) == "ab ab ab "
    #
    r = "<OpImpl `def(i32, str) -> str` for `_testing_helpers::repeat`>"
    assert repr(w_opimpl) == r
    #
    expected = textwrap.dedent("""
    def(v0: i32, v1: str) -> str:
        return `_testing_helpers::repeat`(v1, v0)
    """).strip()
    assert w_opimpl.render() == expected


def test_const():
    vm = SPyVM()
    w_repeat = make_w_repeat(vm)
    w_functype = W_FuncType.parse("def(i32) -> str")
    w_s: W_Object = vm.wrap("ab ")
    w_opimpl = W_OpImpl(
        w_functype, w_repeat, [ArgSpec.Const(w_s, Loc.here()), ArgSpec.Arg(0)]
    )
    w_s = w_opimpl._execute(vm, [vm.wrap(3)])
    assert vm.unwrap_str(w_s) == "ab ab ab "
    expected = textwrap.dedent("""
    def(v0: i32) -> str:
        return `_testing_helpers::repeat`(W_Str('ab '), v0)
    """).strip()
    assert w_opimpl.render() == expected


def test_converter():
    vm = SPyVM()
    w_repeat = make_w_repeat(vm)

    # Create a converter opimpl for f64->i32
    # It takes 3 args (expT, gotT, value) but only passes the value to w_f64_to_i32
    w_conv_functype = W_FuncType.parse("def(type, type, f64) -> i32")
    w_conv_opimpl = W_OpImpl(
        w_conv_functype,
        OP.w_f64_to_i32,
        [ArgSpec.Arg(2)],
    )

    w_functype = W_FuncType.parse("def(f64, str) -> str")
    expT = ArgSpec.Const(B.w_i32, Loc.here())
    gotT = ArgSpec.Const(B.w_str, Loc.here())
    w_opimpl = W_OpImpl(
        w_functype,
        w_repeat,
        [
            ArgSpec.Arg(1),
            ArgSpec.Convert(w_conv_opimpl, expT, gotT, ArgSpec.Arg(0)),
        ],
    )
    w_s = w_opimpl._execute(vm, [vm.wrap(3.5), vm.wrap("ab ")])
    assert vm.unwrap_str(w_s) == "ab ab ab "
    #
    expected = textwrap.dedent("""
    def(v0: f64, v1: str) -> str:
        return `_testing_helpers::repeat`(v1, `operator::f64_to_i32`(v0))
    """).strip()
    assert w_opimpl.render() == expected
