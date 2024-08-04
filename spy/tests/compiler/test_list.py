#-*- encoding: utf-8 -*-

import pytest
from spy.vm.b import B
from spy.vm.object import W_Type
from spy.tests.support import CompilerTest, only_interp, no_C

# Eventually we want to remove the @only_interp, but for now the C backend
# doesn't support lists
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
        assert w_list_i32.pyclass.__name__ == 'W_List[W_I32]'

    def test_generalize_literal(self):
        mod = self.compile(
        """
        def foo() -> type:
            x = [i32, f64, str]
            return STATIC_TYPE(x)

        def bar() -> type:
            x = [i32, f64, 'hello']
            return STATIC_TYPE(x)
        """)
        # our machinery unwraps types, let's wrap it again
        w_t1 = self.vm.wrap(mod.foo())
        assert w_t1.name == 'list[type]'
        w_t2 = self.vm.wrap(mod.bar())
        assert w_t2.name == 'list[object]'

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
        def foo(i: i32) -> list[i32]:
            x: list[i32] = [0, 1, 2]
            x[i] = x[i] + 10
            return x
        """)
        assert mod.foo(0) == [10, 1, 2]
        assert mod.foo(1) == [0, 11, 2]

    def test_eq(self):
        mod = self.compile(
        """
        A: list[i32] = [0, 1, 2]
        B: list[type] = [i32, f64, str]

        def cmp_i32(x: i32) -> bool:
            c: list[i32] = [0, 1, x]
            return A == c

        def cmp_types(x: type) -> bool:
            c: list[type] = [i32, f64, x]
            return B == c
        """)
        assert mod.cmp_i32(2) == True
        assert mod.cmp_i32(3) == False
        assert mod.cmp_types(B.w_str) == True
        assert mod.cmp_types(B.w_i32) == False

    def test_interp_repr(self):
        mod = self.compile(
        """
        def foo() -> list[i32]:
            return [1, 2]
        """)
        w_foo = mod.foo.w_func
        w_l = self.vm.call_function(w_foo, [])
        assert repr(w_l) == 'W_List[W_I32]([W_I32(1), W_I32(2)])'
