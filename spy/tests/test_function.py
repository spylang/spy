import pytest
from spy.vm.vm import SPyVM
from spy.vm.codeobject import W_CodeObject, OpCode
from spy.vm.function import W_FunctionType, W_Function


class TestFunction:

    def test_FunctionType_repr(self):
        vm = SPyVM()
        w_i32 = vm.builtins.w_i32
        w_functype = W_FunctionType([w_i32, w_i32], w_i32)
        assert w_functype.name == 'fn (i32, i32) -> i32'
        assert repr(w_functype) == "<spy type 'fn (i32, i32) -> i32'>"

    def test_simple_function(self):
        vm = SPyVM()
        w_functype = W_FunctionType([], vm.builtins.w_i32)
        #
        w_code = W_CodeObject('simple')
        w_code.body = [
            OpCode('i32_const', vm.wrap(42)),
            OpCode('return'),
        ]
        #
        w_func = W_Function(w_functype, w_code)
        assert repr(w_func) == "<spy function 'simple'>"
        #
        w_t = vm.dynamic_type(w_func)
        assert w_t is w_functype
