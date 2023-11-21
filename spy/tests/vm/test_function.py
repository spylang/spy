import pytest
from spy.fqn import FQN
from spy.vm.vm import SPyVM, Builtins as B
from spy.vm.codeobject import W_CodeObject, OpCode
from spy.vm.function import W_FuncType, W_UserFunc, FuncParam
from spy.vm.module import W_Module
from spy.tests.support import make_func


class TestFunction:

    def test_FunctionType_repr(self):
        w_functype = W_FuncType.make(x=B.w_i32, y=B.w_i32, w_restype=B.w_i32)
        assert w_functype.name == 'def(x: i32, y: i32) -> i32'
        assert repr(w_functype) == "<spy type 'def(x: i32, y: i32) -> i32'>"

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

    def test_simple_function(self):
        vm = SPyVM()
        w_func = make_func(
            'def() -> i32',
            body = [
                OpCode('load_const', vm.wrap(42)),
                OpCode('return'),
            ]
        )
        assert repr(w_func) == "<spy function 'test::fn'>"
        w_t = vm.dynamic_type(w_func)
        assert w_t == W_FuncType.make(w_restype=B.w_i32)

    def test_make_and_call_function(self):
        vm = SPyVM()
        w_mod = W_Module(vm, 'mymod', 'mymod.spy')
        vm.register_module(w_mod)
        vm.add_global(FQN('mymod::a'),
                      B.w_i32,
                      vm.wrap(10))
        w_func = make_func(
            'def() -> i32',
            body = [
                OpCode('load_global', FQN('mymod::a')),
                OpCode('return'),
            ]
        )
        w_result = vm.call_function(w_func, [])
        assert vm.unwrap(w_result) == 10

    def test_call_function_with_arguments(self):
        vm = SPyVM()
        w_mod = W_Module(vm, 'mymod', 'mymod.spy')
        w_func = make_func(
            'def(a: i32, b: i32) -> i32',
            body = [
                OpCode('load_const', B.w_i32),
                OpCode('declare_local', 'a'),
                OpCode('store_local', 'a'),
                OpCode('load_const', B.w_i32),
                OpCode('declare_local', 'b'),
                OpCode('store_local', 'b'),
                #
                OpCode('load_local', 'a'),
                OpCode('load_local', 'b'),
                OpCode('i32_sub'),
                OpCode('return'),
            ]
        )
        w_result = vm.call_function(w_func, [vm.wrap(100), vm.wrap(80)])
        assert vm.unwrap(w_result) == 20
