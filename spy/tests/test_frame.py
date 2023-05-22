from spy.vm.opcode import OpCode, CodeObject
from spy.vm.frame import Frame
from spy.vm.vm import SPyVM

class TestFrame:

    def test_simple_eval(self):
        vm = SPyVM()
        w_42 = vm.wrap(42)
        body = [
            OpCode('i32_const', w_42),
            OpCode('return'),
        ]
        code = CodeObject('simple', body)
        frame = Frame(vm, code)
        w_result = frame.eval()
        assert w_result is w_42

    def test_i32_add(self):
        vm = SPyVM()
        w_100 = vm.wrap(100)
        w_1 = vm.wrap(1)
        body = [
            OpCode('i32_const', w_100),
            OpCode('i32_const', w_1),
            OpCode('i32_add'),
            OpCode('return'),
        ]
        code = CodeObject('simple', body)
        frame = Frame(vm, code)
        w_result = frame.eval()
        result = vm.unwrap(w_result)
        assert result == 101
