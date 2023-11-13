import pytest
from spy.fqn import FQN
from spy.vm.vm import SPyVM, Builtins as B
from spy.vm.codeobject import OpCode, W_CodeObject
from spy.vm.function import W_FunctionType, W_UserFunction
from spy.rainbow import RainbowInterpreter

class TestRainbow:

    def rainbow_peval(self, vm, w_func):
        self.rainbow = RainbowInterpreter(vm, w_func)
        return self.rainbow.run()

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
        w_func2 = self.rainbow_peval(vm, w_func)
        assert vm.call_function(w_func2, []) == w_42
        assert w_func2.w_code.equals("""
        0 load_const W_i32(42)
        1 return
        """)
