#-*- encoding: utf-8 -*-

import pytest
from spy.vm.object import W_Type
from spy.tests.support import CompilerTest, no_C

@no_C
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
