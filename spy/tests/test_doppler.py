import pytest
from spy.fqn import FQN
from spy.vm.vm import SPyVM, Builtins as B
from spy.vm.codeobject import OpCode, W_CodeObject
from spy.vm.object import W_i32
from spy.vm.function import W_FuncType, W_UserFunc
from spy.doppler import DopplerInterpreter

@pytest.mark.usefixtures('init')
class TestDoppler:

    @pytest.fixture
    def init(self):
        self.vm = SPyVM()

    def make_func(self, ft: str, body: list[OpCode]):
        w_functype = W_FuncType.parse(ft)
        code = W_CodeObject(FQN('test::fn'), w_functype=w_functype)
        code.body = body
        w_func = W_UserFunc(code)
        return w_func

    def doppler(self, w_func: W_UserFunc) -> W_UserFunc:
        self.interp = DopplerInterpreter(self.vm, w_func)
        return self.interp.run()

    def test_simple(self):
        w_func = self.make_func(
            'def() -> i32',
            body=[
                OpCode('load_const', W_i32(42)),
                OpCode('return'),
            ]
        )
        w_func2 = self.doppler(w_func)
        w_res = self.vm.call_function(w_func2, [])
        assert self.vm.unwrap(w_res) == 42
        assert w_func2.w_code.equals("""
        load_const W_i32(42)
        return
        """)
