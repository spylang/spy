import pytest

from spy.fqn import FQN
from spy.tests.support import CompilerTest, no_C
from spy.vm.b import B
from spy.vm.modules.__spy__.interp_list import W_InterpListType


# as the name suggests, interp_list works only in the interpreter and is not supported
# by the C backend
@no_C
class TestInterpList(CompilerTest):
    def test_generic_type(self):
        mod = self.compile("""
        from __spy__ import interp_list

        @blue
        def foo():
            return interp_list[i32]
        """)
        w_foo = mod.foo.w_func
        w_list_i32 = self.vm.fast_call(w_foo, [])
        assert isinstance(w_list_i32, W_InterpListType)
        assert w_list_i32.fqn == FQN("__spy__::interp_list[i32]")

    def test_new(self):
        mod = self.compile("""
        from __spy__ import interp_list

        def new_empty() -> interp_list[i32]:
            x = interp_list[i32]()
            return x

        def new_with_values(x: i32, y: i32, z: i32) -> interp_list[i32]:
            return interp_list[i32](x, y, z)
        """)
        l1 = mod.new_empty()
        assert l1 == []
        l2 = mod.new_with_values(1, 2, 3)
        assert l2 == [1, 2, 3]

    def test_getitem(self):
        mod = self.compile("""
        from __spy__ import interp_list

        def foo(i: i32) -> str:
            x = interp_list[str]("foo", "bar", "baz")
            return x[i]
        """)
        assert mod.foo(0) == "foo"
        assert mod.foo(1) == "bar"

    def test_setitem(self):
        mod = self.compile("""
        from __spy__ import interp_list

        def foo(i: i32) -> interp_list[i32]:
            x = interp_list[i32](0, 1, 2)
            x[i] = x[i] + 10
            return x
        """)
        assert mod.foo(0) == [10, 1, 2]
        assert mod.foo(1) == [0, 11, 2]

    def test_eq(self):
        if self.backend == "doppler":
            pytest.skip("list PBCs not supported")

        mod = self.compile("""
        from __spy__ import interp_list

        A = interp_list[i32](0, 1, 2)
        B = interp_list[type](i32, f64, str)

        def cmp_i32(x: i32) -> bool:
            c = interp_list[i32](0, 1, x)
            return A == c

        def cmp_types(x: type) -> bool:
            c = interp_list[type](i32, f64, x)
            return B == c
        """)
        assert mod.cmp_i32(2) == True
        assert mod.cmp_i32(3) == False
        assert mod.cmp_types(B.w_str) == True
        assert mod.cmp_types(B.w_i32) == False

    def test_add(self):
        mod = self.compile("""
        from __spy__ import interp_list

        def add_i32_lists() -> interp_list[i32]:
            a = interp_list[i32](0, 1)
            b = interp_list[i32](2, 3)
            return a + b

        def add_str_lists() -> interp_list[str]:
            a = interp_list[str]("a")
            b = interp_list[str]("b", "bb")
            c = interp_list[str]("c", "cc", "ccc")
            return a + b + c

        def test_iadd_lists() -> interp_list[str]:
            a = interp_list[str]("a")
            b = interp_list[str]("b", "bb")
            a += b
            return a

        def add_type_lists_repr() -> str:
            a = interp_list[type](i32, f64)
            b = interp_list[type](bool)
            return repr(a + b)
        """)

        assert mod.add_i32_lists() == [0, 1, 2, 3]
        assert mod.add_str_lists() == ["a", "b", "bb", "c", "cc", "ccc"]
        assert mod.test_iadd_lists() == ["a", "b", "bb"]
        assert (
            mod.add_type_lists_repr()
            == "[<spy type 'i32'>, <spy type 'f64'>, <spy type 'bool'>]"
        )

    def test_repr_str(self):
        mod = self.compile("""
        from __spy__ import interp_list

        def str_list_str(a: str, b: str) -> str:
            x = interp_list[str](a, b)
            return str(x)

        def repr_list_str(a: str, b: str) -> str:
            x = interp_list[str](a, b)
            return repr(x)

        def str_list_i32(a: i32, b: i32) -> str:
            x = interp_list[i32](a, b)
            return str(x)

        def repr_list_i32(a: i32, b: i32) -> str:
            x = interp_list[i32](a, b)
            return repr(x)
        """)
        assert mod.str_list_str("aaa", "bbb") == "['aaa', 'bbb']"
        assert mod.repr_list_str("aaa", "bbb") == "['aaa', 'bbb']"
        assert mod.str_list_i32(1, 2) == "[1, 2]"
        assert mod.repr_list_i32(1, 2) == "[1, 2]"

    def test_interp_repr(self):
        mod = self.compile("""
        from __spy__ import interp_list

        def foo() -> interp_list[i32]:
            return interp_list[i32](1, 2)
        """)
        w_foo = mod.foo.w_func
        w_l = self.vm.fast_call(w_foo, [])
        assert repr(w_l) == "W_InterpList('i32', [W_I32(1), W_I32(2)])"
