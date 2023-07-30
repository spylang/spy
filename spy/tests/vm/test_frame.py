import pytest
from typing import Optional
from spy.errors import SPyRuntimeError
from spy.vm.vm import SPyVM
from spy.vm.object import W_Object
from spy.vm.frame import Frame
from spy.vm.codeobject import OpCode, W_CodeObject
from spy.vm.varstorage import VarStorage
from spy.vm.function import W_FunctionType

def make_Frame(vm: SPyVM, w_code: W_Object,
               globals: Optional[VarStorage] = None) -> Frame:
    """
    Like Frame(), but allows to pass None for globals
    """
    if globals is None:
        globals = VarStorage(vm, 'globals', {})
    return Frame(vm, w_code, globals)

class TestFrame:

    def test_simple_eval(self):
        vm = SPyVM()
        w_42 = vm.wrap(42)
        w_functype = W_FunctionType.make(w_restype=vm.builtins.w_i32)
        code = W_CodeObject('simple', w_functype=w_functype)
        code.body = [
            OpCode('load_const', w_42),
            OpCode('return'),
        ]
        frame = make_Frame(vm, code)
        w_result = frame.run([])
        assert w_result is w_42

    def test_i32_add(self):
        vm = SPyVM()
        w_100 = vm.wrap(100)
        w_1 = vm.wrap(1)
        w_functype = W_FunctionType.make(w_restype=vm.builtins.w_i32)
        code = W_CodeObject('simple', w_functype=w_functype)
        code.body = [
            OpCode('load_const', w_100),
            OpCode('load_const', w_1),
            OpCode('i32_add'),
            OpCode('return'),
        ]
        frame = make_Frame(vm, code)
        w_result = frame.run([])
        result = vm.unwrap(w_result)
        assert result == 101

    def test_i32_sub(self):
        vm = SPyVM()
        w_50 = vm.wrap(50)
        w_8 = vm.wrap(8)
        w_functype = W_FunctionType.make(w_restype=vm.builtins.w_i32)
        code = W_CodeObject('simple', w_functype=w_functype)
        code.body = [
            OpCode('load_const', w_50),
            OpCode('load_const', w_8),
            OpCode('i32_sub'),
            OpCode('return'),
        ]
        frame = make_Frame(vm, code)
        w_result = frame.run([])
        result = vm.unwrap(w_result)
        assert result == 42

    def test_uninitialized_locals(self):
        vm = SPyVM()
        w_functype = W_FunctionType.make(w_restype=vm.builtins.w_i32)
        code = W_CodeObject('simple', w_functype=w_functype)
        code.declare_local('a', vm.builtins.w_i32)
        code.body = [
            OpCode('load_local', 'a'),
            OpCode('return'),
        ]
        frame = make_Frame(vm, code)
        with pytest.raises(SPyRuntimeError,
                           match='read from uninitialized local'):
            w_result = frame.run([])

    def test_locals(self):
        vm = SPyVM()
        w_100 = vm.wrap(100)
        w_functype = W_FunctionType.make(w_restype=vm.builtins.w_i32)
        code = W_CodeObject('simple', w_functype=w_functype)
        code.declare_local('a', vm.builtins.w_i32)
        code.body = [
            OpCode('load_const', w_100),
            OpCode('store_local', 'a'),
            OpCode('load_local', 'a'),
            OpCode('return'),
        ]
        frame = make_Frame(vm, code)
        w_result = frame.run([])
        assert w_result is w_100

    def test_globals(self):
        vm = SPyVM()
        w_functype = W_FunctionType.make(w_restype=vm.builtins.w_i32)
        code = W_CodeObject('simple', w_functype=w_functype)
        code.body = [
            OpCode('load_global', 'a'),
            OpCode('load_const', vm.wrap(11)),
            OpCode('i32_add'),
            OpCode('store_global', 'b'),
            OpCode('load_const', vm.wrap(0)),
            OpCode('return'),
        ]

        globals_w_types = {
            'a': vm.builtins.w_i32,
            'b': vm.builtins.w_i32,
        }
        myglobs = VarStorage(vm, 'globals', globals_w_types)
        myglobs.set('a', vm.wrap(100))

        frame = Frame(vm, code, myglobs)
        w_result = frame.run([])
        assert vm.unwrap(w_result) == 0
        assert vm.unwrap(myglobs.get('b')) == 111

    def test_params(self):
        vm = SPyVM()
        w_i32 = vm.builtins.w_i32
        w_functype = W_FunctionType.make(a=w_i32, b=w_i32, w_restype=w_i32)
        code = W_CodeObject('simple', w_functype=w_functype)
        code.declare_local('a', w_i32)
        code.declare_local('b', w_i32)
        code.body = [
            OpCode('load_local', 'a'),
            OpCode('load_local', 'b'),
            OpCode('i32_sub'),
            OpCode('return'),
        ]
        #
        w_50 = vm.wrap(50)
        w_8 = vm.wrap(8)
        frame = make_Frame(vm, code)
        w_result = frame.run([w_50, w_8])
        result = vm.unwrap(w_result)
        assert result == 42

    def test_br_if_not(self):
        vm = SPyVM()
        w_bool = vm.builtins.w_bool
        w_i32 = vm.builtins.w_i32
        w_functype = W_FunctionType.make(a=w_bool, w_restype=w_i32)
        code = W_CodeObject('simple', w_functype=w_functype)
        code.declare_local('a', w_bool)
        code.body = [
            OpCode('load_local', 'a'),           # 0
            OpCode('br_if_not', 4),              # 1
            OpCode('load_const', vm.wrap(100)),  # 2
            OpCode('return'),                    # 3
            OpCode('load_const', vm.wrap(200)),  # 4
            OpCode('return'),                    # 5
        ]
        frame1 = make_Frame(vm, code)
        w_result = frame1.run([vm.builtins.w_True])
        result = vm.unwrap(w_result)
        assert result == 100
        #
        frame2 = make_Frame(vm, code)
        w_result = frame2.run([vm.builtins.w_False])
        result = vm.unwrap(w_result)
        assert result == 200
