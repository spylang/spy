import pytest
from typing import Annotated
from spy.errors import SPyError
from spy.vm.object import W_Object
from spy.vm.primitive import W_I32, W_Dynamic
from spy.vm.vm import SPyVM
from spy.vm.w import W_FuncType, W_BuiltinFunc, W_Str
from spy.vm.b import B
from spy.fqn import FQN
from spy.vm.builtin import (
    functype_from_sig,
    builtin_type,
    builtin_method,
    builtin_class_attr
)

class TestBuiltin:

    def test_functype_from_sig(self):
        def foo(vm: 'SPyVM', w_x: W_I32) -> W_Str:
            return W_Str(vm, 'this is never called')
        w_functype = functype_from_sig(foo, 'red', 'plain')
        assert w_functype == W_FuncType.parse('def(i32) -> str')

    def test_functype_from_sig_extra_types(self):
        def foo(vm: 'SPyVM', w_x: W_I32) -> 'FooBar':  # type: ignore
            return W_Str(vm, 'this is never called')
        extra_types = {
            'FooBar': W_Str
        }
        w_functype = functype_from_sig(foo, 'red', 'plain', extra_types=extra_types)
        assert w_functype == W_FuncType.parse('def(i32) -> str')

    def test_annotated_type(self):
        W_MyType = Annotated[W_Object, B.w_i32]
        def foo(vm: 'SPyVM', w_x: W_MyType) -> None:
            pass
        w_functype = functype_from_sig(foo, 'red', 'plain')
        assert w_functype == W_FuncType.parse('def(i32) -> None')

    def test_builtin_func(self):
        vm = SPyVM()

        @vm.register_builtin_func('_testing_helpers')
        def w_foo(vm: 'SPyVM', w_x: W_I32) -> W_I32:
            x = vm.unwrap_i32(w_x)
            return vm.wrap(x*2)

        assert isinstance(w_foo, W_BuiltinFunc)
        assert w_foo.fqn == FQN('_testing_helpers::foo')
        w_y = vm.fast_call(w_foo, [vm.wrap(10)])
        assert vm.unwrap_i32(w_y) == 20

    def test_builtin_func_errors(self):
        vm = SPyVM()
        with pytest.raises(ValueError,
                           match="The first param should be 'vm: SPyVM'."):
            @vm.register_builtin_func('mymod')
            def w_foo() -> W_I32:  # type: ignore
                pass

        with pytest.raises(ValueError,
                           match="The first param should be 'vm: SPyVM'."):
            @vm.register_builtin_func('mymod')
            def w_foo(w_x: W_I32) -> W_I32:  # type: ignore
                pass

        with pytest.raises(
                ValueError,
                match="Invalid @builtin_func annotation: <class 'int'>"):
            @vm.register_builtin_func('mymod')
            def w_foo(vm: 'SPyVM', x: int) -> W_I32:  # type: ignore
                pass

        with pytest.raises(
                ValueError,
                match="Invalid @builtin_func annotation: <class 'int'>"):
            @vm.register_builtin_func('mymod')
            def w_foo(vm: 'SPyVM') -> int:  # type: ignore
                pass

    def test_builtin_func_dynamic(self):
        vm = SPyVM()
        @vm.register_builtin_func('_testing_helpers')
        def w_foo(vm: 'SPyVM', w_x: W_Dynamic) -> W_Dynamic:  # type: ignore
            pass
        assert w_foo.w_functype.fqn.human_name == 'def(dynamic) -> dynamic'

    def test_return_None(self):
        vm = SPyVM()
        @vm.register_builtin_func('_testing_helpers')
        def w_foo(vm: 'SPyVM') -> None:
            pass
        assert w_foo.w_functype.fqn.human_name == 'def() -> None'
        assert isinstance(w_foo, W_BuiltinFunc)
        w_res = vm.fast_call(w_foo, [])
        assert w_res is B.w_None

    def test_blue(self):
        vm = SPyVM()

        @vm.register_builtin_func('_testing_helpers', color='blue')
        def w_foo(vm: 'SPyVM', w_x: W_I32) -> W_I32:
            x = vm.unwrap_i32(w_x)
            return vm.wrap(x*2)

        assert w_foo.w_functype.fqn.human_name == '@blue def(i32) -> i32'
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
        assert w_foo.lookup_func('make') is w_make
        assert isinstance(w_make, W_BuiltinFunc)
        assert w_make.w_functype.fqn.human_name == "def() -> test::Foo"
        assert w_make.w_functype.w_restype is W_Foo._w

    def test_builtin_class_attr(self):
        vm = SPyVM()
        w_42 = vm.wrap(42)

        @builtin_type('test', 'Foo')
        class W_Foo(W_Object):
            w_attr = builtin_class_attr('attr', w_42)

        assert W_Foo.w_attr is w_42
        assert W_Foo._w.dict_w['attr'] is w_42


    def test_inherit_method(self):
        @builtin_type('test', 'Super')
        class W_Super(W_Object):

            @builtin_method('foo')
            @staticmethod
            def w_foo(vm: 'SPyVM') -> None:
                pass

        @builtin_type('test', 'Sub')
        class W_Sub(W_Super):
            pass

        w_super = W_Super._w
        w_sub = W_Sub._w

        w_foo = w_super.dict_w['foo']
        assert w_super.lookup_func('foo') is w_foo
        assert w_sub.lookup_func('foo') is w_foo

    def test_metafunc_wrong_color(self):
        class W_Foo(W_Object):

            @builtin_method('__getitem__', kind='metafunc')
            @staticmethod
            def w_GETITEM(vm: 'SPyVM') -> 'W_Foo':
                return W_Foo()

        msg = ("wrong color for metafunc `test::Foo::__getitem__`: "
               "expected `blue`, got `red`")
        with SPyError.raises('W_TypeError', match=msg):
            # simulate @decorator application
            builtin_type('test', 'Foo')(W_Foo)
