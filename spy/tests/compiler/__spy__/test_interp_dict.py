import pytest

from spy.fqn import FQN
from spy.tests.support import CompilerTest, no_C
from spy.vm.b import B
from spy.vm.modules.__spy__.interp_dict import W_InterpDictType


@no_C
class TestInterpDict(CompilerTest):
    def test_generic_type(self):
        mod = self.compile("""
        from __spy__ import interp_dict

        @blue
        def foo():
            return interp_dict[str, i32]
        """)
        w_foo = mod.foo.w_func
        w_dict_str_i32 = self.vm.fast_call(w_foo, [])
        assert isinstance(w_dict_str_i32, W_InterpDictType)
        assert w_dict_str_i32.fqn == FQN("__spy__::interp_dict[str, i32]")

    def test_new(self):
        mod = self.compile("""
        from __spy__ import interp_dict

        def new_empty() -> interp_dict[str, i32]:
            x = interp_dict[str, i32]()
            return x
        """)
        d = mod.new_empty()
        assert d == {}

    def test_getitem_setitem(self):
        mod = self.compile("""
        from __spy__ import interp_dict

        def foo() -> i32:
            d = interp_dict[str, i32]()
            d["hello"] = 10
            d["world"] = 20
            return d["hello"] + d["world"]
        """)
        assert mod.foo() == 30

    def test_eq(self):
        mod = self.compile("""
        from __spy__ import interp_dict

        def cmp_str_i32(val: i32) -> bool:
            c = interp_dict[str, i32]()
            c["a"] = 1
            c["b"] = val
            d = interp_dict[str, i32]()
            d["a"] = 1
            d["b"] = 2
            return c == d
        """)
        assert mod.cmp_str_i32(2) == True
        assert mod.cmp_str_i32(3) == False

    def test_len(self):
        mod = self.compile("""
        from __spy__ import interp_dict

        def test_len() -> i32:
            d = interp_dict[str, i32]()
            d["a"] = 1
            d["b"] = 2
            d["c"] = 3
            return len(d)
        """)
        assert mod.test_len() == 3

    def test_contains(self):
        pytest.skip(
            "'in' operator not yet implemented; __contains__ can't be called directly"
        )
        mod = self.compile("""
        from __spy__ import interp_dict

        def test_contains() -> bool:
            d = interp_dict[str, i32]()
            d["hello"] = 42
            return "hello" in d

        def test_not_contains() -> bool:
            d = interp_dict[str, i32]()
            d["hello"] = 42
            return "world" in d
        """)
        assert mod.test_contains() == True
        assert mod.test_not_contains() == False

    def test_repr_str(self):
        mod = self.compile("""
        from __spy__ import interp_dict

        def str_dict(a: str, b: i32) -> str:
            d = interp_dict[str, i32]()
            d[a] = b
            return str(d)

        def repr_dict(a: str, b: i32) -> str:
            d = interp_dict[str, i32]()
            d[a] = b
            return repr(d)

        def str_empty_dict() -> str:
            d = interp_dict[str, i32]()
            return str(d)
        """)
        assert mod.str_dict("key", 42) == "{'key': 42}"
        assert mod.repr_dict("key", 42) == "{'key': 42}"
        assert mod.str_empty_dict() == "{}"

    def test_interp_repr(self):
        mod = self.compile("""
        from __spy__ import interp_dict

        def foo() -> interp_dict[str, i32]:
            d = interp_dict[str, i32]()
            d["a"] = 1
            d["b"] = 2
            return d
        """)
        w_foo = mod.foo.w_func
        w_d = self.vm.fast_call(w_foo, [])
        assert "W_InterpDict" in repr(w_d)
        assert "'str'" in repr(w_d)
        assert "'i32'" in repr(w_d)

    def test_type_as_key(self):
        mod = self.compile("""
        from __spy__ import interp_dict

        def test_type_keys() -> i32:
            d = interp_dict[type, i32]()
            d[i32] = 10
            d[f64] = 20
            d[str] = 30
            return d[i32] + d[f64] + d[str]
        """)
        assert mod.test_type_keys() == 60

    def test_type_as_value(self):
        mod = self.compile("""
        from __spy__ import interp_dict

        def test_type_values() -> type:
            d = interp_dict[str, type]()
            d["int"] = i32
            d["float"] = f64
            d["string"] = str
            return d["int"]
        """)
        w_result = mod.test_type_values(unwrap=False)
        assert w_result is B.w_i32

    def test_empty_dict_conversion(self):
        src = """
        from __spy__ import interp_dict

        def foo() -> interp_dict[str, i32]:
            d: interp_dict[str, i32] = {}
            return d
        """
        mod = self.compile(src)
        res = mod.foo()
        assert res == {}
