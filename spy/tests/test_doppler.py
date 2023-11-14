import pytest
from spy.fqn import FQN
from spy.vm.vm import SPyVM, Builtins as B
from spy.vm.codeobject import OpCode, W_CodeObject
from spy.vm.function import W_FunctionType, W_UserFunction
from spy.doppler import DopplerInterpreter

class TestDoppler:

    def doppler(self, vm: SPyVM,
                      w_func: W_UserFunction) -> W_UserFunction:
        self.interp = DopplerInterpreter(vm, w_func)
        return self.interp.run()

    def test_simple(self):
        vm = SPyVM()
        w_42 = vm.wrap(42)
        w_functype = W_FunctionType.make(w_restype=B.w_i32)
        code = W_CodeObject(FQN('test::fn'), w_functype=w_functype)
        code.body = [
            OpCode('load_const', w_42),
            OpCode('return'),
        ]
        w_func = W_UserFunction(code)
        w_func2 = self.doppler(vm, w_func)
        assert vm.call_function(w_func2, []) == w_42
        assert w_func2.w_code.equals("""
        0 load_const W_i32(42)
        1 return
        """)
