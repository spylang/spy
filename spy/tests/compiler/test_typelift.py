import pytest
from spy.errors import SPyError
from spy.tests.support import (CompilerTest, only_interp)

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
        from operator import OpSpec

        @typelift
        class MyInt:
            __ll__: i32

            @blue.metafunc
            def __getitem__(m_obj, m_i):
                def getitem(m: MyInt, i: i32) -> i32:
                    return m.__ll__ + i*2
                return OpSpec(getitem)

        def foo(x: i32, y: i32) -> i32:
            m = MyInt.__lift__(x)
            return m[y]
        """)
        assert mod.foo(30, 6) == 42

    def test_method(self):
        src = """
        from operator import OpSpec

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

    def test_if_inside_classdef(self):
        src = """
        @blue
        def make_Foo(DOUBLE):
            @typelift
            class Foo:
                __ll__: i32

                def __new__(i: i32) -> Foo:
                    return Foo.__lift__(i)

                if DOUBLE:
                    def get(self: Foo) -> i32:
                        return self.__ll__ * 2
                else:
                    def get(self: Foo) -> i32:
                        return self.__ll__

            return Foo

        def test1(x: i32) -> i32:
            a = make_Foo(True)(x)
            return a.get()

        def test2(x: i32) -> i32:
            b = make_Foo(False)(x)
            return b.get()
        """
        mod = self.compile(src)
        assert mod.test1(10) == 20
        assert mod.test2(10) == 10

    def test_staticmethod(self):
        src = """
        from operator import OpSpec

        @typelift
        class MyInt:
            __ll__: i32

            @staticmethod
            def one() -> MyInt:
                return MyInt.__lift__(1)

            @staticmethod
            def from_pair(x: i32, y: i32) -> MyInt:
                return MyInt.__lift__(x + y)

            @staticmethod
            @blue.metafunc
            def from_many(*args_m):
                if len(args_m) == 3:
                    def from3(x: i32, y: i32, z: i32) -> MyInt:
                        return MyInt.__lift__(x + y + z)
                    return OpSpec(from3)
                raise TypeError('invalid number of args')

        def one() -> i32:
            m = MyInt.one()
            return m.__ll__

        def from_pair(x: i32, y: i32) -> i32:
            m = MyInt.from_pair(x, y)
            return m.__ll__

        def from_triple(x: i32, y: i32, z: i32) -> i32:
            m = MyInt.from_many(x, y, z)
            return m.__ll__

        def from_quadruple(x: i32, y: i32, z: i32, w: i32) -> i32:
            # this raises TypeError
            MyInt.from_many(x, y, z, w)
            return 9999 # never reached
        """
        mod = self.compile(src, error_mode='lazy')
        assert mod.one() == 1
        assert mod.from_pair(4, 5) == 9
        assert mod.from_triple(4, 5, 6) == 15
        with SPyError.raises('W_TypeError', match='invalid number of args'):
            mod.from_quadruple(4, 5, 6, 7)
