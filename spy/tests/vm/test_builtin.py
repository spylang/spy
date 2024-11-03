import pytest
from spy.vm.vm import SPyVM
from spy.vm.w import W_FuncType, W_I32, W_BuiltinFunc, W_Dynamic, W_Str
from spy.vm.b import B
from spy.fqn import QN
from spy.vm.builtin import builtin_func, functype_from_sig

class TestBuiltin:

    def test_functype_from_sig(self):
        def foo(vm: 'SPyVM', w_x: W_I32) -> W_Str:
            return W_Str(vm, 'this is never called')
        w_functype = functype_from_sig(foo, 'red')
        assert w_functype == W_FuncType.parse('def(x: i32) -> str')

    def test_builtin_func(self):
        vm = SPyVM()

        @builtin_func(QN('test::foo'))
        def w_foo(vm: 'SPyVM', w_x: W_I32) -> W_I32:
            x = vm.unwrap_i32(w_x)
            return vm.wrap(x*2)  # type: ignore

        assert isinstance(w_foo, W_BuiltinFunc)
        assert w_foo.qn == QN('test::foo')
        w_y = vm.call(w_foo, [vm.wrap(10)])
        assert vm.unwrap_i32(w_y) == 20

    def test_builtin_func_errors(self):
        with pytest.raises(ValueError,
                           match="The first param should be 'vm: SPyVM'."):
            @builtin_func(QN('test::foo'))
            def w_foo() -> W_I32:  # type: ignore
                pass

        with pytest.raises(ValueError,
                           match="The first param should be 'vm: SPyVM'."):
            @builtin_func(QN('test::foo'))
            def w_foo(w_x: W_I32) -> W_I32:  # type: ignore
                pass

        with pytest.raises(ValueError, match="Invalid param: 'x: int'"):
            @builtin_func(QN('test::foo'))
            def w_foo(vm: 'SPyVM', x: int) -> W_I32:  # type: ignore
                pass

        with pytest.raises(ValueError, match="Invalid return type"):
            @builtin_func(QN('test::foo'))
            def w_foo(vm: 'SPyVM') -> int:  # type: ignore
                pass

    def test_builtin_func_dynamic(self):
        vm = SPyVM()
        @builtin_func(QN('test::foo'))
        def w_foo(vm: 'SPyVM', w_x: W_Dynamic) -> W_Dynamic:  # type: ignore
            pass
        assert w_foo.w_functype.name == 'def(x: dynamic) -> dynamic'

    def test_return_None(self):
        vm = SPyVM()
        @builtin_func(QN('test::foo'))
        def w_foo(vm: 'SPyVM') -> None:
            pass
        assert w_foo.w_functype.name == 'def() -> void'
        assert isinstance(w_foo, W_BuiltinFunc)
        w_res = vm.call(w_foo, [])
        assert w_res is B.w_None

    def test_blue(self):
        vm = SPyVM()

        @builtin_func(QN('test::foo'), color='blue')
        def w_foo(vm: 'SPyVM', w_x: W_I32) -> W_I32:
            x = vm.unwrap_i32(w_x)
            return vm.wrap(x*2)  # type: ignore

        assert w_foo.w_functype.name == '@blue def(x: i32) -> i32'
        w_x = vm.call(w_foo, [vm.wrap(21)])
        w_y = vm.call(w_foo, [vm.wrap(21)])
        assert w_x is w_y