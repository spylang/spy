from typing import Optional
from spy.vm.vm import SPyVM
from spy.vm.object import W_Object
from spy.vm.frame import Frame
from spy.vm.codeobject import OpCode, W_CodeObject
from spy.vm.varstorage import VarStorage

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
        code = W_CodeObject('simple')
        code.body = [
            OpCode('i32_const', w_42),
            OpCode('return'),
        ]
        frame = make_Frame(vm, code)
        w_result = frame.run([])
        assert w_result is w_42

    def test_i32_add(self):
        vm = SPyVM()
        w_100 = vm.wrap(100)
        w_1 = vm.wrap(1)
        code = W_CodeObject('simple')
        code.body = [
            OpCode('i32_const', w_100),
            OpCode('i32_const', w_1),
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
        code = W_CodeObject('simple')
        code.body = [
            OpCode('i32_const', w_50),
            OpCode('i32_const', w_8),
            OpCode('i32_sub'),
            OpCode('return'),
        ]
        frame = make_Frame(vm, code)
        w_result = frame.run([])
        result = vm.unwrap(w_result)
        assert result == 42

    def test_uninitialized_locals(self):
        vm = SPyVM()
        code = W_CodeObject('simple')
        code.locals_w_types = {
            'a': vm.builtins.w_i32,
        }
        code.body = [
            OpCode('local_get', 'a'),
            OpCode('return'),
        ]
        frame = make_Frame(vm, code)
        w_result = frame.run([])
        result = vm.unwrap(w_result)
        assert result == 0

    def test_locals(self):
        vm = SPyVM()
        w_100 = vm.wrap(100)
        code = W_CodeObject('simple')
        code.locals_w_types = {
            'a': vm.builtins.w_i32,
        }
        code.body = [
            OpCode('i32_const', w_100),
            OpCode('local_set', 'a'),
            OpCode('local_get', 'a'),
            OpCode('return'),
        ]
        frame = make_Frame(vm, code)
        w_result = frame.run([])
        assert w_result is w_100

    def test_globals(self):
        vm = SPyVM()
        code = W_CodeObject('simple')
        code.body = [
            OpCode('global_get', 'a'),
            OpCode('i32_const', vm.wrap(11)),
            OpCode('i32_add'),
            OpCode('global_set', 'b'),
            OpCode('i32_const', vm.wrap(0)),
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
        code = W_CodeObject('simple')
        code.params = ('a', 'b')
        code.locals_w_types = {
            'a': vm.builtins.w_i32,
            'b': vm.builtins.w_i32,
        }
        code.body = [
            OpCode('local_get', 'a'),
            OpCode('local_get', 'b'),
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
