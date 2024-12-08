import pytest
from spy.vm.primitive import W_I32
from spy.vm.vm import SPyVM
from spy.vm.b import B
from spy.vm.w import W_FuncType

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
