import pytest
from typing import Annotated
from spy.vm.object import W_Object
from spy.vm.primitive import W_I32, W_Dynamic
from spy.vm.vm import SPyVM
from spy.vm.w import W_FuncType, W_BuiltinFunc, W_Str
from spy.vm.b import B
from spy.fqn import FQN
from spy.vm.builtin import (builtin_func, functype_from_sig,
                            builtin_type, builtin_method)

class TestBuiltin:

    def test_functype_from_sig(self):
        def foo(vm: 'SPyVM', w_x: W_I32) -> W_Str:
            return W_Str(vm, 'this is never called')
        w_functype = functype_from_sig(foo, 'red')
        assert w_functype == W_FuncType.parse('def(x: i32) -> str')

    def test_functype_from_sig_extra_types(self):
        def foo(vm: 'SPyVM', w_x: W_I32) -> 'FooBar':  # type: ignore
            return W_Str(vm, 'this is never called')
        extra_types = {
            'FooBar': W_Str
        }
        w_functype = functype_from_sig(foo, 'red', extra_types=extra_types)
        assert w_functype == W_FuncType.parse('def(x: i32) -> str')

    def test_annotated_type(self):
        W_MyType = Annotated[W_Object, B.w_i32]
        def foo(vm: 'SPyVM', w_x: W_MyType) -> None:
            pass
        w_functype = functype_from_sig(foo, 'red')
        assert w_functype == W_FuncType.parse('def(x: i32) -> void')

    def test_builtin_func(self):
        vm = SPyVM()

        @builtin_func('mymod')
        def w_foo(vm: 'SPyVM', w_x: W_I32) -> W_I32:
            x = vm.unwrap_i32(w_x)
            return vm.wrap(x*2)  # type: ignore

        assert isinstance(w_foo, W_BuiltinFunc)
        assert w_foo.fqn == FQN('mymod::foo')
        w_y = vm.fast_call(w_foo, [vm.wrap(10)])
        assert vm.unwrap_i32(w_y) == 20

    def test_builtin_func_errors(self):
        with pytest.raises(ValueError,
                           match="The first param should be 'vm: SPyVM'."):
            @builtin_func('mymod')
            def w_foo() -> W_I32:  # type: ignore
                pass

        with pytest.raises(ValueError,
                           match="The first param should be 'vm: SPyVM'."):
            @builtin_func('mymod')
            def w_foo(w_x: W_I32) -> W_I32:  # type: ignore
                pass

        with pytest.raises(
                ValueError,
                match="Invalid @builtin_func annotation: <class 'int'>"):
            @builtin_func('mymod')
            def w_foo(vm: 'SPyVM', x: int) -> W_I32:  # type: ignore
                pass

        with pytest.raises(
                ValueError,
                match="Invalid @builtin_func annotation: <class 'int'>"):
            @builtin_func('mymod')
            def w_foo(vm: 'SPyVM') -> int:  # type: ignore
                pass

    def test_builtin_func_dynamic(self):
        vm = SPyVM()
        @builtin_func('mymod')
        def w_foo(vm: 'SPyVM', w_x: W_Dynamic) -> W_Dynamic:  # type: ignore
            pass
        assert w_foo.w_functype.signature == 'def(x: dynamic) -> dynamic'

    def test_return_None(self):
        vm = SPyVM()
        @builtin_func('mymod')
        def w_foo(vm: 'SPyVM') -> None:
            pass
        assert w_foo.w_functype.signature == 'def() -> void'
        assert isinstance(w_foo, W_BuiltinFunc)
        w_res = vm.fast_call(w_foo, [])
        assert w_res is B.w_None

    def test_blue(self):
        vm = SPyVM()

        @builtin_func('mymod', color='blue')
        def w_foo(vm: 'SPyVM', w_x: W_I32) -> W_I32:
            x = vm.unwrap_i32(w_x)
            return vm.wrap(x*2)  # type: ignore

        assert w_foo.w_functype.signature == '@blue def(x: i32) -> i32'
        w_x = vm.fast_call(w_foo, [vm.wrap(21)])
        w_y = vm.fast_call(w_foo, [vm.wrap(21)])
        assert w_x is w_y

    def test_builtin_method(self):
        @builtin_type('test', 'Foo')
        class W_Foo(W_Object):

            @builtin_method('make')
            @staticmethod
            def w_make(vm: 'SPyVM') -> 'W_Foo':
                return W_Foo()

        w_foo = W_Foo._w
        w_make = w_foo.dict_w['make']
        assert isinstance(w_make, W_BuiltinFunc)
        assert w_make.w_functype.signature == "def() -> test::Foo"
        assert w_make.w_functype.w_restype is W_Foo._w
