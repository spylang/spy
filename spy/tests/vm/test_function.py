import pytest
from spy.vm.vm import SPyVM, Builtins as B
from spy.vm.codeobject import W_CodeObject, OpCode
from spy.vm.function import W_FunctionType, W_Function, FuncParam
from spy.vm.varstorage import VarStorage
from spy.vm.module import W_Module


class TestFunction:

    def test_FunctionType_repr(self):
        vm = SPyVM()
        w_functype = W_FunctionType.make(x=B.w_i32, y=B.w_i32, w_restype=B.w_i32)
        assert w_functype.name == 'def(x: i32, y: i32) -> i32'
        assert repr(w_functype) == "<spy type 'def(x: i32, y: i32) -> i32'>"

    def test_simple_function(self):
        vm = SPyVM()
        w_functype = W_FunctionType([], B.w_i32)
        #
        w_code = W_CodeObject('simple', w_functype=w_functype)
        w_code.body = [
            OpCode('load_const', vm.wrap(42)),
            OpCode('return'),
        ]
        #
        globals = VarStorage(vm, 'globals', {})
        w_func = W_Function(w_code, globals)
        assert repr(w_func) == "<spy function 'simple'>"
        #
        w_t = vm.dynamic_type(w_func)
        assert w_t is w_functype

    def test_make_and_call_function(self):
        vm = SPyVM()
        w_mod = W_Module(vm, 'mymod')
        w_a = vm.wrap(10)
        w_mod.add('a', w_a)
        #
        w_functype = W_FunctionType([], B.w_i32)
        w_code = W_CodeObject('fn', w_functype=w_functype)
        w_code.body = [
            OpCode('load_global', 'a'),
            OpCode('return'),
        ]
        #
        w_fn = vm.make_function(w_code, w_mod)
        assert repr(w_fn) == "<spy function 'fn'>"
        assert w_mod.content.get('fn') is w_fn
        assert w_fn.globals is w_mod.content
        #
        w_result = vm.call_function(w_fn, [])
        assert vm.unwrap(w_result) == 10

    def test_call_function_with_arguments(self):
        vm = SPyVM()
        w_mod = W_Module(vm, 'mymod')
        w_functype = W_FunctionType.make(a=B.w_i32, b=B.w_i32, w_restype=B.w_i32)
        w_code = W_CodeObject('fn', w_functype=w_functype)
        w_code.declare_local('a', B.w_i32)
        w_code.declare_local('b', B.w_i32)
        w_code.body = [
            OpCode('load_local', 'a'),
            OpCode('load_local', 'b'),
            OpCode('i32_sub'),
            OpCode('return'),
        ]
        #
        w_fn = vm.make_function(w_code, w_mod)
        #
        w_result = vm.call_function(w_fn, [vm.wrap(100), vm.wrap(80)])
        assert vm.unwrap(w_result) == 20
