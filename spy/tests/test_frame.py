from spy.vm.vm import SPyVM
from spy.vm.frame import Frame
from spy.vm.codeobject import OpCode, W_CodeObject


class TestFrame:

    def test_simple_eval(self):
        vm = SPyVM()
        w_42 = vm.wrap(42)
        code = W_CodeObject('simple')
        code.body = [
            OpCode('i32_const', w_42),
            OpCode('return'),
        ]
        frame = Frame(vm, code)
        w_result = frame.run()
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
        frame = Frame(vm, code)
        w_result = frame.run()
        result = vm.unwrap(w_result)
        assert result == 101

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
        frame = Frame(vm, code)
        w_result = frame.run()
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
        frame = Frame(vm, code)
        w_result = frame.run()
        assert w_result is w_100
