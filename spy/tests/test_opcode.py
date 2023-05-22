import pytest
from spy.vm.opcode import OpCode, CodeObject

class TestOpCode:

    def test_repr(self):
        op1 = OpCode('return')
        op2 = OpCode('i32_const', 1, 2, 3, 4)
        assert repr(op1) == '<OpCode return>'
        assert repr(op2) == '<OpCode i32_const [1, 2, 3, 4]>'

    def test_invalid_name(self):
        with pytest.raises(ValueError, match='Invalid opcode: xxx'):
            op = OpCode('xxx')
