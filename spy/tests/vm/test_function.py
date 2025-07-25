from typing import no_type_check
from spy.fqn import FQN
from spy.vm.object import W_Type
from spy.vm.vm import SPyVM
from spy.vm.b import B
from spy.vm.w import W_FuncType
from spy.vm.function import W_ASTFunc, FuncParam, FuncKind, Color


def make_FuncType(
        *types_w: W_Type,
        w_restype: W_Type,
        color: Color = 'red',
        kind: FuncKind = 'plain',
) -> W_FuncType:
    """
    Small helper to make it easier to build W_FuncType.
    """
    params = [
        FuncParam(w_type, 'simple')
        for w_type in types_w
    ]
    return W_FuncType.new(params, w_restype, color=color, kind=kind)


class TestFunction:

    def test_FunctionType_repr(self):
        w_functype = make_FuncType(B.w_i32, B.w_i32, w_restype=B.w_bool)
        assert str(w_functype.fqn) == 'builtins::def[i32, i32, bool]'
        assert repr(w_functype) == "<spy type 'def(i32, i32) -> bool'>"

    def test_FunctionType_parse(self):
        w_ft = W_FuncType.parse('def() -> i32')
        assert w_ft == make_FuncType(w_restype=B.w_i32)
        #
        w_ft = W_FuncType.parse('def(str) -> i32')
        assert w_ft == make_FuncType(B.w_str, w_restype=B.w_i32)
        #
        w_ft = W_FuncType.parse('def(str, i32,) -> i32')
        assert w_ft == make_FuncType(
            B.w_str,
            B.w_i32,
            w_restype = B.w_i32
        )

    def test_FunctionType_eq(self):
        vm = SPyVM()
        w_ft1 = W_FuncType.parse('def() -> i32')
        w_ft2 = W_FuncType.parse('def() -> i32')
        assert w_ft1 is not w_ft2
        assert w_ft1 == w_ft2
        w_res = vm.eq(w_ft1, w_ft2)
        assert w_res is B.w_True

    @no_type_check
    def test_function_eq(self):
        class FakeFuncDef:
            prototype_loc = None
        funcdef = FakeFuncDef()

        vm = SPyVM()
        w_functype = W_FuncType.parse('def() -> i32')
        w_a = W_ASTFunc(w_functype, FQN('test::a'), funcdef, closure=None)
        w_b = W_ASTFunc(w_functype, FQN('test::b'), funcdef, closure=None)
        assert vm.eq(w_a, w_a) is B.w_True
        assert vm.eq(w_a, w_b) is B.w_False

    def test_FunctionType_fqn(self):
        def make(color: Color, kind: FuncKind):
            return make_FuncType(
                B.w_i32,
                B.w_i32,
                w_restype = B.w_str,
                color = color,
                kind = kind
            )
        w_t1 = make('red', 'plain')
        assert w_t1.fqn == FQN('builtins::def[i32, i32, str]')
        assert w_t1.fqn.human_name == 'def(i32, i32) -> str'

        w_t2 = make('blue', 'plain')
        assert w_t2.fqn == FQN('builtins::blue.def[i32, i32, str]')
        assert w_t2.fqn.human_name == '@blue def(i32, i32) -> str'

        w_t3 = make('blue', 'generic')
        assert w_t3.fqn == FQN('builtins::blue.generic.def[i32, i32, str]')
        assert w_t3.fqn.human_name == '@blue.generic def(i32, i32) -> str'
