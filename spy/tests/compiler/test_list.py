#-*- encoding: utf-8 -*-

import pytest
from spy.vm.object import W_Type
from spy.tests.support import CompilerTest, only_interp

@only_interp
class TestList(CompilerTest):

    def test_generic_type(self):
        mod = self.compile(
        """
        @blue
        def foo():
            return list[i32]
        """)
        w_foo = mod.foo.w_func
        w_list_i32 = self.vm.call_function(w_foo, [])
        assert isinstance(w_list_i32, W_Type)
        assert w_list_i32.name == 'list[i32]'

    def test_literal(self):
        mod = self.compile(
        """
        def foo() -> list[i32]:
            x: list[i32] = [1, 2, 3]
            return x
        """)
        x = mod.foo()
        assert x == [1, 2, 3]

    def test_getitem(self):
        mod = self.compile(
        """
        def foo(i: i32) -> str:
            x: list[str] = ["foo", "bar", "baz"]
            return x[i]
        """)
        assert mod.foo(0) == "foo"
        assert mod.foo(1) == "bar"

    def test_setitem(self):
        mod = self.compile(
        """
        def foo(i: i32) -> i32:
            x: list[i32] = [0, 1, 2]
            x[i] = x[i] + 10
            return x
        """)
        assert mod.foo(0) == [10, 1, 2]
        assert mod.foo(1) == [0, 11, 2]
