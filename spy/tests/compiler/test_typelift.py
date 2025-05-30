import re
import pytest
from spy.fqn import FQN
from spy.errors import SPyError
from spy.vm.b import B
from spy.vm.function import W_ASTFunc
from spy.tests.support import (CompilerTest, skip_backends,  expect_errors,
                               only_interp)

class TestTypelift(CompilerTest):

    @only_interp
    def test_repr(self):
        mod = self.compile("""
        @typelift
        class MyInt:
            __ll__: i32

        def get() -> type:
            return MyInt
        """)
        w_myint = mod.get(unwrap=False)
        assert repr(w_myint) == "<spy type 'test::MyInt' (lifted from 'i32')>"

    def test_lift_and_lower(self):
        mod = self.compile("""
        @typelift
        class MyInt:
            __ll__: i32

        def lift(i: i32) -> MyInt:
            return MyInt.__lift__(i)

        def lower(m: MyInt) -> i32:
            return m.__ll__

        def call_lower(i: i32) -> i32:
            return lower(lift(i))

        """)
        myint = mod.lift(42)
        assert myint.llval == 42
        assert myint.w_hltype.fqn.fullname == 'test::MyInt'
        assert mod.call_lower(43) == 43

    def test_operator(self):
        mod = self.compile("""
        from operator import OpImpl

        @typelift
        class MyInt:
            __ll__: i32

            @blue
            def __GETITEM__(v_obj, v_i):
                def getitem(m: MyInt, i: i32) -> i32:
                    return m.__ll__ + i*2
                return OpImpl(getitem)

        def foo(x: i32, y: i32) -> i32:
            m = MyInt.__lift__(x)
            return m[y]
        """)
        assert mod.foo(30, 6) == 42

    def test_method(self):
        src = """
        from operator import OpImpl

        @typelift
        class MyInt:
            __ll__: i32

            def __new__(x: i32) -> MyInt:
                return MyInt.__lift__(x)

            def double(self: MyInt) -> i32:
                return self.__ll__ * 2

        def foo(x: i32) -> i32:
            m = MyInt(x)
            return m.double()

        def wrong_args(x: i32) -> i32:
            m = MyInt(x)
            return m.double(1, 2, 3)

        def wrong_meth(x: i32) -> i32:
            m = MyInt(x)
            return m.dont_exist()
        """
        mod = self.compile(src, error_mode="lazy")
        assert mod.foo(10) == 20

        msg = 'this function takes 1 argument but 4 arguments were supplied'
        with SPyError.raises('W_TypeError', match=msg):
            mod.wrong_args(10)

        msg = 'method `test::MyInt::dont_exist` does not exist'
        with SPyError.raises('W_TypeError', match=msg):
            mod.wrong_meth(10)
