import pytest
from typing import Optional
from spy.fqn import FQN
from spy.errors import SPyRuntimeError
from spy.vm.vm import SPyVM, Builtins as B
from spy.vm.object import W_Object
from spy.vm.frame import Frame
from spy.vm.codeobject import OpCode, W_CodeObject
from spy.vm.function import W_FunctionType
from spy.vm.module import W_Module

class TestFrame:

    def test_simple_eval(self):
        vm = SPyVM()
        w_42 = vm.wrap(42)
        w_functype = W_FunctionType.make(w_restype=B.w_i32)
        code = W_CodeObject('simple', w_functype=w_functype)
        code.body = [
            OpCode('load_const', w_42),
            OpCode('return'),
        ]
        frame = Frame(vm, code)
        w_result = frame.run([])
        assert w_result is w_42

    def test_i32_add(self):
        vm = SPyVM()
        w_100 = vm.wrap(100)
        w_1 = vm.wrap(1)
        w_functype = W_FunctionType.make(w_restype=B.w_i32)
        code = W_CodeObject('simple', w_functype=w_functype)
        code.body = [
            OpCode('load_const', w_100),
            OpCode('load_const', w_1),
            OpCode('i32_add'),
            OpCode('return'),
        ]
        frame = Frame(vm, code)
        w_result = frame.run([])
        result = vm.unwrap(w_result)
        assert result == 101

    def test_i32_sub(self):
        vm = SPyVM()
        w_50 = vm.wrap(50)
        w_8 = vm.wrap(8)
        w_functype = W_FunctionType.make(w_restype=B.w_i32)
        code = W_CodeObject('simple', w_functype=w_functype)
        code.body = [
            OpCode('load_const', w_50),
            OpCode('load_const', w_8),
            OpCode('i32_sub'),
            OpCode('return'),
        ]
        frame = Frame(vm, code)
        w_result = frame.run([])
        result = vm.unwrap(w_result)
        assert result == 42

    def test_uninitialized_locals(self):
        vm = SPyVM()
        w_functype = W_FunctionType.make(w_restype=B.w_i32)
        code = W_CodeObject('simple', w_functype=w_functype)
        code.declare_local('a', B.w_i32)
        code.body = [
            OpCode('load_local', 'a'),
            OpCode('return'),
        ]
        frame = Frame(vm, code)
        with pytest.raises(SPyRuntimeError,
                           match='read from uninitialized local'):
            w_result = frame.run([])

    def test_locals(self):
        vm = SPyVM()
        w_100 = vm.wrap(100)
        w_functype = W_FunctionType.make(w_restype=B.w_i32)
        code = W_CodeObject('simple', w_functype=w_functype)
        code.declare_local('a', B.w_i32)
        code.body = [
            OpCode('load_const', w_100),
            OpCode('store_local', 'a'),
            OpCode('load_local', 'a'),
            OpCode('return'),
        ]
        frame = Frame(vm, code)
        w_result = frame.run([])
        assert w_result is w_100

    def test_globals(self):
        vm = SPyVM()
        w_mod = W_Module(vm, 'mymod')
        vm.register_module(w_mod)
        w_functype = W_FunctionType.make(w_restype=B.w_i32)
        code = W_CodeObject('simple', w_functype=w_functype)

        mymod_a = FQN('mymod::a')
        mymod_b = FQN('mymod::b')
        code.body = [
            OpCode('load_global', mymod_a),
            OpCode('load_const', vm.wrap(11)),
            OpCode('i32_add'),
            OpCode('store_global', mymod_b),
            OpCode('load_const', vm.wrap(0)),
            OpCode('return'),
        ]

        vm.add_global(mymod_a, B.w_i32, vm.wrap(100))
        vm.add_global(mymod_b, B.w_i32, vm.wrap(0))
        frame = Frame(vm, code)
        w_result = frame.run([])
        assert vm.unwrap(w_result) == 0
        assert vm.unwrap(vm.lookup_global(mymod_b)) == 111

    def test_params(self):
        vm = SPyVM()
        w_functype = W_FunctionType.make(a=B.w_i32, b=B.w_i32, w_restype=B.w_i32)
        code = W_CodeObject('simple', w_functype=w_functype)
        code.declare_local('a', B.w_i32)
        code.declare_local('b', B.w_i32)
        code.body = [
            OpCode('load_local', 'a'),
            OpCode('load_local', 'b'),
            OpCode('i32_sub'),
            OpCode('return'),
        ]
        #
        w_50 = vm.wrap(50)
        w_8 = vm.wrap(8)
        frame = Frame(vm, code)
        w_result = frame.run([w_50, w_8])
        result = vm.unwrap(w_result)
        assert result == 42

    def test_br_if_not(self):
        vm = SPyVM()
        w_functype = W_FunctionType.make(a=B.w_bool, w_restype=B.w_i32)
        code = W_CodeObject('simple', w_functype=w_functype)
        code.declare_local('a', B.w_bool)
        code.body = [
            OpCode('load_local', 'a'),           # 0
            OpCode('br_if_not', 4),              # 1
            OpCode('load_const', vm.wrap(100)),  # 2
            OpCode('return'),                    # 3
            OpCode('load_const', vm.wrap(200)),  # 4
            OpCode('return'),                    # 5
        ]
        frame1 = Frame(vm, code)
        w_result = frame1.run([B.w_True])
        result = vm.unwrap(w_result)
        assert result == 100
        #
        frame2 = Frame(vm, code)
        w_result = frame2.run([B.w_False])
        result = vm.unwrap(w_result)
        assert result == 200
