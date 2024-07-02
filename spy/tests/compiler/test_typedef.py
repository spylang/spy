import re
import pytest
from spy.errors import SPyTypeError
from spy.fqn import QN
from spy.vm.b import B
from spy.vm.function import W_ASTFunc
from spy.vm.modules.types import W_TypeDef
from spy.tests.support import (CompilerTest, skip_backends,  expect_errors,
                               only_interp)

class TestTypeDef(CompilerTest):

    def test_cast_from_and_to(self):
        # XXX: for now we allow implicit coversion between a TypeDef and it's
        # origin type because it's simpler, but eventually we want a more
        # explicit way, e.g. TypeDef.cast or something like that.
        mod = self.compile("""
        from types import makeTypeDef
        MyInt = makeTypeDef('MyInt', i32, [])

        # this should go away and become MyInt.cast_from
        def MyInt_cast_from(x: i32) -> MyInt:
            return x

        # same as above
        def MyInt_cast_to(x: MyInt) -> i32:
            return x

        def foo() -> MyInt:
            x: MyInt = MyInt_cast_from(42)
            return x

        def bar() -> i32:
            x: MyInt = MyInt_cast_from(43)
            return MyInt_cast_to(x)
        """)
        assert mod.foo() == 42
        assert mod.bar() == 43

    @only_interp
    def test_metaclass_setattr(self):
        """
        Test that we can succesfully set attributes on the typedef itself
        """
        mod = self.compile("""
        from types import makeTypeDef

        @blue
        def makeMyInt():
            MyInt = makeTypeDef('MyInt', i32, [])

            @blue
            def __getattr__(attr):
                return NotImplemented

            MyInt.__getattr__ = __getattr__
            return MyInt
        """)
        w_makeMyInt = mod.makeMyInt.w_func
        w_MyInt = self.vm.call_function(w_makeMyInt, [])
        assert isinstance(w_MyInt, W_TypeDef)
        w_getattr = w_MyInt.w_getattr
        assert isinstance(w_getattr, W_ASTFunc)
        assert w_getattr.qn == QN("test::__getattr__")
        w_res = self.vm.call_function(w_getattr, [B.w_None])
        assert w_res is B.w_NotImplemented

    @only_interp
    def test_metaclass_getattr(self):
        """
        Test that we can succesfully get attributes on the typedef itself
        """
        mod = self.compile("""
        from types import makeTypeDef

        @blue
        def foo():
            MyInt = makeTypeDef('MyInt', i32, [])
            MyInt.__getattr__ = 42
            return MyInt.__getattr__
        """)
        w_foo = mod.foo.w_func
        w_res = self.vm.call_function(w_foo, [])
        assert self.vm.unwrap(w_res) == 42

    def test_getattr(self):
        mod = self.compile("""
        from types import makeTypeDef

        @blue
        def makeMyInt():
            MyInt = makeTypeDef('MyInt', i32, [])

            def getattr_double(self: MyInt, attr: str) -> i32:
                i: i32 = self
                return i * 2

            @blue
            def __getattr__(self, attr):
                if attr == "double":
                    return getattr_double
                return NotImplemented

            MyInt.__getattr__ = __getattr__
            return MyInt

        MyInt = makeMyInt()

        def foo(x: i32) -> i32:
            y: MyInt = x
            return y.double
        """)
        assert mod.foo(10) == 20

    def test_setattr(self):
        mod = self.compile("""
        from types import makeTypeDef
        from rawbuffer import RawBuffer, rb_alloc, rb_get_i32, rb_set_i32

        @blue
        def makeBox():
            Box = makeTypeDef('Box', RawBuffer, [])

            def getattr_x(self: Box, attr: str) -> i32:
                buf: RawBuffer = self
                return rb_get_i32(buf, 0)

            def setattr_x(self: Box, attr: str, value: i32) -> void:
                buf: RawBuffer = self
                rb_set_i32(buf, 0, value)

            @blue
            def __getattr__(self, attr):
                if attr == "x":
                    return getattr_x
                return NotImplemented

            @blue
            def __setattr__(self, attr, vtype):
                if attr == "x":
                    return setattr_x
                return NotImplemented

            Box.__getattr__ = __getattr__
            Box.__setattr__ = __setattr__
            return Box

        Box = makeBox()

        def foo(value: i32) -> i32:
            buf: RawBuffer = rb_alloc(4)
            b: Box = buf
            b.x = value
            return b.x
        """)
        assert mod.foo(10) == 10
