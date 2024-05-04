import pytest
from spy.vm.vm import SPyVM
from spy.vm.w import W_FuncType, W_I32, W_BuiltinFunc, W_Dynamic, W_Str
from spy.vm.b import B
from spy.fqn import QN
from spy.vm.sig import spy_builtin, functype_from_sig

class TestSig:

    def test_functype_from_sig(self):
        def foo(vm: 'SPyVM', w_x: W_I32) -> W_Str:
            pass
        w_functype = functype_from_sig(foo)
        assert w_functype == W_FuncType.parse('def(x: i32) -> str')

    def test_spy_builtin(self):
        vm = SPyVM()

        @spy_builtin(QN('test::foo'))
        def foo(vm: 'SPyVM', w_x: W_I32) -> W_I32:
            x = vm.unwrap_i32(w_x)
            return vm.wrap(x*2)  # type: ignore

        w_x = foo(vm, vm.wrap(21))
        assert vm.unwrap_i32(w_x) == 42

        w_foo = vm.wrap(foo)
        assert isinstance(w_foo, W_BuiltinFunc)
        assert w_foo.qn == QN('test::foo')
        w_y = vm.call_function(w_foo, [vm.wrap(10)])
        assert vm.unwrap_i32(w_y) == 20

    def test_spy_builtin_errors(self):
        with pytest.raises(ValueError,
                           match="The first param should be 'vm: SPyVM'."):
            @spy_builtin(QN('test::foo'))
            def foo() -> W_I32:  # type: ignore
                pass

        with pytest.raises(ValueError,
                           match="The first param should be 'vm: SPyVM'."):
            @spy_builtin(QN('test::foo'))
            def foo(w_x: W_I32) -> W_I32:  # type: ignore
                pass

        with pytest.raises(ValueError, match="Invalid param: 'x: int'"):
            @spy_builtin(QN('test::foo'))
            def foo(vm: 'SPyVM', x: int) -> W_I32:  # type: ignore
                pass

        with pytest.raises(ValueError, match="Invalid return type"):
            @spy_builtin(QN('test::foo'))
            def foo(vm: 'SPyVM') -> int:  # type: ignore
                pass

    def test_spy_builtin_dynamic(self):
        vm = SPyVM()
        @spy_builtin(QN('test::foo'))
        def foo(vm: 'SPyVM', w_x: W_Dynamic) -> W_Dynamic:  # type: ignore
            pass
        assert foo.w_functype.name == 'def(x: dynamic) -> dynamic'

    def test_return_None(self):
        vm = SPyVM()
        @spy_builtin(QN('test::foo'))
        def foo(vm: 'SPyVM') -> None:
            pass
        assert foo.w_functype.name == 'def() -> void'
        assert foo(vm) is None
        #
        w_foo = vm.wrap(foo)
        w_res = vm.call_function(w_foo, [])
        assert w_res is B.w_None
