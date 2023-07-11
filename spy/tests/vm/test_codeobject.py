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

    def test_set_args(self):
        op = OpCode('br_if_not', ...)
        op.set_args(42)
        assert op.args == (42,)
        with pytest.raises(ValueError, match='Cannot set args on a fully constructed op'):
            op.set_args(43)

    def test_match(self):
        op = OpCode('load_local', 'a')
        assert op.match('load_local', 'a')
        assert op.match('load_local', ...)
        assert not op.match('load_local')
        assert not op.match('i32_add')
