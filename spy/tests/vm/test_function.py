import pytest
from spy.vm.vm import SPyVM
from spy.vm.b import B
from spy.vm.w import W_FuncType, W_I32, W_BuiltinFunc
from spy.fqn import FQN
from spy.vm.function import W_FuncType, spy_builtin

class TestFunction:

    def test_FunctionType_repr(self):
        w_functype = W_FuncType.make(x=B.w_i32, y=B.w_i32, w_restype=B.w_i32)
        assert w_functype.name == 'def(x: i32, y: i32) -> i32'
        assert repr(w_functype) == "<spy type 'def(x: i32, y: i32) -> i32'>"

    def test_FunctionType_parse(self):
        w_ft = W_FuncType.parse('def() -> i32')
        assert w_ft == W_FuncType.make(w_restype=B.w_i32)
        #
        w_ft = W_FuncType.parse('def(x: str) -> i32')
        assert w_ft == W_FuncType.make(x=B.w_str, w_restype=B.w_i32)
        #
        w_ft = W_FuncType.parse('def(x: str, y: i32,) -> i32')
        assert w_ft == W_FuncType.make(x=B.w_str,
                                           y=B.w_i32,
                                           w_restype=B.w_i32)


    def test_spy_builtin(self):
        vm = SPyVM()

        @spy_builtin(FQN('test::foo'))
        def foo(vm: 'SPyVM', w_x: W_I32) -> W_I32:
            x = vm.unwrap_i32(w_x)
            return vm.wrap(x*2)

        w_x = foo(vm, vm.wrap(21))
        assert vm.unwrap_i32(w_x) == 42

        w_foo = vm.wrap(foo)
        assert isinstance(w_foo, W_BuiltinFunc)
        assert w_foo.fqn == FQN('test::foo')
        w_y = vm.call_function(w_foo, [vm.wrap(10)])
        assert vm.unwrap_i32(w_y) == 20

    def test_spy_builtin_errors(self):
        with pytest.raises(ValueError,
                           match="The first param should be 'vm: SPyVM'."):
            @spy_builtin(FQN('test::foo'))
            def foo() -> W_I32:
                pass

        with pytest.raises(ValueError,
                           match="The first param should be 'vm: SPyVM'."):
            @spy_builtin(FQN('test::foo'))
            def foo(w_x: W_I32) -> W_I32:
                pass

        with pytest.raises(ValueError, match="Invalid param: 'x: int'"):
            @spy_builtin(FQN('test::foo'))
            def foo(vm: 'SPyVM', x: int) -> W_I32:
                pass

        with pytest.raises(ValueError, match="Invalid return type"):
            @spy_builtin(FQN('test::foo'))
            def foo(vm: 'SPyVM') -> int:
                pass
