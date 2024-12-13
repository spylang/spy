import pytest
from typing import no_type_check
from spy.fqn import FQN
from spy.vm.primitive import W_I32
from spy.vm.vm import SPyVM
from spy.vm.b import B
from spy.vm.w import W_FuncType
from spy.vm.function import W_ASTFunc

class TestFunction:

    def test_FunctionType_repr(self):
        w_functype = W_FuncType.make(x=B.w_i32, y=B.w_i32, w_restype=B.w_bool)
        assert str(w_functype.fqn) == 'builtins::def[i32, i32, bool]'
        assert repr(w_functype) == "<spy type 'def(x: i32, y: i32) -> bool'>"

    def test_FunctionType_parse(self):
        w_ft = W_FuncType.parse('def() -> i32')
        assert w_ft == W_FuncType.make(w_restype=B.w_i32)
        #
        w_ft = W_FuncType.parse('def(x: str) -> i32')
        assert w_ft == W_FuncType.make(x=B.w_str, w_restype=B.w_i32)
        #
        w_ft = W_FuncType.parse('def(x: str, y: i32,) -> i32')
        assert w_ft == W_FuncType.make(x=B.w_str,
                                           y=B.w_i32,
                                           w_restype=B.w_i32)

    @pytest.mark.xfail(reason='implement me')
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
        vm = SPyVM()
        w_functype = W_FuncType.parse('def() -> i32')
        w_a = W_ASTFunc(w_functype, FQN('test::a'), funcdef=None, closure=None)
        w_b = W_ASTFunc(w_functype, FQN('test::b'), funcdef=None, closure=None)
        assert vm.eq(w_a, w_a) is B.w_True
        assert vm.eq(w_a, w_b) is B.w_False
