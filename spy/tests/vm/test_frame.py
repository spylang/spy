import pytest
from typing import Optional
from spy.fqn import FQN
from spy.errors import SPyRuntimeError
from spy.vm.vm import SPyVM, Builtins as B
from spy.vm.object import W_Object
from spy.vm.frame import Frame
from spy.vm.codeobject import OpCode, W_CodeObject
from spy.vm.function import W_FuncType
from spy.vm.module import W_Module
from spy.tests.support import make_func

class TestFrame:

    def test_simple_eval(self):
        vm = SPyVM()
        w_42 = vm.wrap(42)
        w_func = make_func(
            'def() -> i32',
            body = [
                OpCode('load_const', w_42),
                OpCode('return'),
            ]
        )
        frame = Frame(vm, w_func)
        w_result = frame.run([])
        assert w_result is w_42

    def test_i32_add(self):
        vm = SPyVM()
        w_100 = vm.wrap(100)
        w_1 = vm.wrap(1)
        w_func = make_func(
            'def() -> i32',
            body = [
                OpCode('load_const', w_100),
                OpCode('load_const', w_1),
                OpCode('i32_add'),
                OpCode('return'),
            ]
        )
        frame = Frame(vm, w_func)
        w_result = frame.run([])
        result = vm.unwrap(w_result)
        assert result == 101

    def test_i32_sub(self):
        vm = SPyVM()
        w_50 = vm.wrap(50)
        w_8 = vm.wrap(8)
        w_func = make_func(
            'def() -> i32',
            body = [
                OpCode('load_const', w_50),
                OpCode('load_const', w_8),
                OpCode('i32_sub'),
                OpCode('return'),
            ]
        )
        frame = Frame(vm, w_func)
        w_result = frame.run([])
        result = vm.unwrap(w_result)
        assert result == 42

    def test_uninitialized_locals(self):
        vm = SPyVM()
        w_func = make_func(
            'def() -> i32',
            body = [
                OpCode('load_const', B.w_i32),
                OpCode('declare_local', 'a'),
                OpCode('load_local', 'a'),
                OpCode('return'),
            ]
        )
        frame = Frame(vm, w_func)
        with pytest.raises(SPyRuntimeError,
                           match='read from uninitialized local'):
            w_result = frame.run([])

    def test_locals(self):
        vm = SPyVM()
        w_100 = vm.wrap(100)
        w_func = make_func(
            'def() -> i32',
            body = [
                OpCode('load_const', B.w_i32),
                OpCode('declare_local', 'a'),
                OpCode('load_const', w_100),
                OpCode('store_local', 'a'),
                OpCode('load_local', 'a'),
                OpCode('return'),
            ]
        )
        frame = Frame(vm, w_func)
        w_result = frame.run([])
        assert w_result is w_100

    def test_globals(self):
        vm = SPyVM()
        w_mod = W_Module(vm, 'mymod', 'mymod.spy')
        vm.register_module(w_mod)
        mymod_a = FQN('mymod::a')
        mymod_b = FQN('mymod::b')
        w_func = make_func(
            'def() -> i32',
            body = [
                OpCode('load_global', mymod_a),
                OpCode('load_const', vm.wrap(11)),
                OpCode('i32_add'),
                OpCode('store_global', mymod_b),
                OpCode('load_const', vm.wrap(0)),
                OpCode('return'),
            ]
        )
        vm.add_global(mymod_a, B.w_i32, vm.wrap(100))
        vm.add_global(mymod_b, B.w_i32, vm.wrap(0))
        frame = Frame(vm, w_func)
        w_result = frame.run([])
        assert vm.unwrap(w_result) == 0
        w_b = vm.lookup_global(mymod_b)
        assert w_b is not None
        assert vm.unwrap(w_b) == 111

    def test_params(self):
        vm = SPyVM()
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
        w_50 = vm.wrap(50)
        w_8 = vm.wrap(8)
        frame = Frame(vm, w_func)
        w_result = frame.run([w_50, w_8])
        result = vm.unwrap(w_result)
        assert result == 42

    def test_br_if(self):
        vm = SPyVM()
        w_func = make_func(
            'def(a: bool) -> i32',
            body = [
                OpCode('load_const', B.w_bool),
                OpCode('declare_local', 'a'),
                OpCode('store_local', 'a'),
                #
                OpCode('load_local', 'a'),
                OpCode('br_if', 'then_0', 'else_0', 'endif_0'),
                OpCode('label', 'then_0'),
                OpCode('load_const', vm.wrap(100)),
                OpCode('return'),
                OpCode('label', 'else_0'),
                OpCode('load_const', vm.wrap(200)),
                OpCode('return'),
                OpCode('label', 'endif_0'),
                OpCode('abort', 'unreachable'),
            ]
        )
        frame1 = Frame(vm, w_func)
        w_result = frame1.run([B.w_True])
        result = vm.unwrap(w_result)
        assert result == 100
        #
        frame2 = Frame(vm, w_func)
        w_result = frame2.run([B.w_False])
        result = vm.unwrap(w_result)
        assert result == 200
