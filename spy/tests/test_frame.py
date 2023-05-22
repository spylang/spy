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
