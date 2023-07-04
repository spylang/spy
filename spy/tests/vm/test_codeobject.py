import pytest
from spy.vm.codeobject import OpCode

class TestOpCode:

    def test_repr(self):
        op1 = OpCode('return')
        op2 = OpCode('load_const', 1, 2, 3, 4)
        assert repr(op1) == '<OpCode return>'
        assert repr(op2) == '<OpCode load_const [1, 2, 3, 4]>'

    def test_invalid_name(self):
        with pytest.raises(ValueError, match='Invalid opcode: xxx'):
            op = OpCode('xxx')

    def test_set_br_target(self):
        op = OpCode('br_if_not', None)
        op.set_br_target(42)
        assert op.args == (42,)
        with pytest.raises(ValueError, match='target already set'):
            op.set_br_target(43)
        #
        op = OpCode('i32_add')
        with pytest.raises(ValueError, match='cannot set br target on opcode i32_add'):
            op.set_br_target(42)
