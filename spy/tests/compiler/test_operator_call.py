import pytest
from spy.fqn import QN
from spy.vm.b import B
from spy.vm.object import spytype, Member, Annotated
from spy.vm.sig import spy_builtin
from spy.vm.w import W_Type, W_Object, W_Dynamic, W_Str, W_I32, W_Void
from spy.vm.list import W_BaseList
from spy.vm.registry import ModuleRegistry
from spy.vm.vm import SPyVM
from spy.tests.support import CompilerTest, no_C

@no_C
class TestCallOp(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def test_call_instance(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry('ext', '<ext>')

        @spytype('Adder')
        class W_Adder(W_Object):

            def __init__(self, x: int) -> None:
                self.x = x

            @staticmethod
            def op_CALL(vm: 'SPyVM', w_type: W_Type,
                        w_argtypes: W_Dynamic) -> W_Dynamic:
                @spy_builtin(QN('ext::call'))
                def call(vm: 'SPyVM', w_obj: W_Adder, w_y: W_I32) -> W_I32:
                    y = vm.unwrap_i32(w_y)
                    res = w_obj.x + y
                    return vm.wrap(res) # type: ignore
                return vm.wrap(call)

        EXT.add('Adder', W_Adder._w)

        @EXT.builtin
        def make(vm: 'SPyVM', w_x: W_I32) -> W_Adder:
            return W_Adder(vm.unwrap_i32(w_x))
        # ========== /EXT module for this test =========
        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import make, Adder

        def foo(x: i32, y: i32) -> i32:
            obj: Adder = make(x)
            return obj(y)
        """)
        x = mod.foo(5, 7)
        assert x == 12


    def test_call_type(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry('ext', '<ext>')

        @spytype('Point')
        class W_Point(W_Object):
            w_x: Annotated[W_I32, Member('x')]
            w_y: Annotated[W_I32, Member('y')]

            def __init__(self, w_x: W_I32, w_y: W_I32) -> None:
                self.w_x = w_x
                self.w_y = w_y

            @staticmethod
            def meta_op_CALL(vm: 'SPyVM', w_type: W_Type,
                             w_argtypes: W_Dynamic) -> W_Dynamic:
                @spy_builtin(QN('ext::new'))
                def new(vm: 'SPyVM', w_cls: W_Type,
                        w_x: W_I32, w_y: W_I32) -> W_Point:
                    return W_Point(w_x, w_y)
                return vm.wrap(new)

        EXT.add('Point', W_Point._w)

        # ========== /EXT module for this test =========
        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import Point

        @blue
        def foo(x: i32, y: i32) -> i32:
            p = Point(x, y)
            return p.x * 10 + p.y
        """)
        res = mod.foo(3, 6)
        assert res == 36

    def test_spy_new(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry('ext', '<ext>')

        @spytype('Point')
        class W_Point(W_Object):
            w_x: Annotated[W_I32, Member('x')]
            w_y: Annotated[W_I32, Member('y')]

            def __init__(self, w_x: W_I32, w_y: W_I32) -> None:
                self.w_x = w_x
                self.w_y = w_y

            @staticmethod
            def spy_new(vm: 'SPyVM', w_cls: W_Type,
                        w_x: W_I32, w_y: W_I32) -> 'W_Point':
                return W_Point(w_x, w_y)

        EXT.add('Point', W_Point._w)

        # ========== /EXT module for this test =========
        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import Point

        @blue
        def foo(x: i32, y: i32) -> i32:
            p = Point(x, y)
            return p.x * 10 + p.y
        """)
        res = mod.foo(3, 6)
        assert res == 36


    def test_call_method(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry('ext', '<ext>')

        @spytype('Calc')
        class W_Calc(W_Object):

            def __init__(self, x: int) -> None:
                self.x = x

            @staticmethod
            def op_CALL_METHOD(vm: 'SPyVM', w_type: W_Type, w_method: W_Str,
                               w_argtypes: W_Dynamic) -> W_Dynamic:

                meth = vm.unwrap_str(w_method)
                if meth == 'add':
                    @spy_builtin(QN('ext::meth_add'))
                    def opimpl(vm: 'SPyVM', w_self: W_Calc, w_method: W_Str,
                               w_arg: W_I32) -> W_I32:
                        y = vm.unwrap_i32(w_arg)
                        return vm.wrap(w_self.x + y)
                    return vm.wrap(opimpl)

                elif meth == 'sub':
                    @spy_builtin(QN('ext::meth_sub'))
                    def opimpl(vm: 'SPyVM', w_self: W_Calc, w_method: W_Str,
                               w_arg: W_I32) -> W_I32:
                        y = vm.unwrap_i32(w_arg)
                        return vm.wrap(w_self.x - y)
                    return vm.wrap(opimpl)

                else:
                    return B.w_NotImplemented

        EXT.add('Calc', W_Calc._w)

        @EXT.builtin
        def make(vm: 'SPyVM', w_x: W_I32) -> W_Calc:
            return W_Calc(vm.unwrap_i32(w_x))
        # ========== /EXT module for this test =========

        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import make, Calc

        def foo(x: i32, y: i32, z: i32) -> i32:
            obj: Calc = make(x)
            return obj.add(y) * 10 + obj.sub(z)
        """)
        x = mod.foo(5, 1, 2)
        assert x == 63
