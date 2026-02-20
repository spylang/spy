from spy.fqn import FQN
from spy.tests.support import CompilerTest, only_interp
from spy.vm.b import B
from spy.vm.object import W_Type


class TestDict(CompilerTest):
    """
    These are only few of the tests about dict, mostly to check that:

      1. dict[K, V] does the right thing

      2. the dict literal syntax "{k: v, ...}" works

    The actual behavior of dict objects is tested by stdlib/test_dict.py and
    test_interp_dict.py
    """

    @only_interp
    def test_dict_type(self):
        src = """
        from _dict import dict as stdlib_dict
        from __spy__ import interp_dict

        def dict_i32_i32() -> type:
            return stdlib_dict[i32, i32]

        def dict_type_i32() -> type:
            return interp_dict[type, i32]
        """
        mod = self.compile(src)
        w_T1 = mod.dict_i32_i32(unwrap=False)
        assert w_T1.fqn == FQN("_dict::dict[i32, i32]::_dict")
        assert w_T1.is_struct(self.vm)

        w_T2 = mod.dict_type_i32(unwrap=False)
        assert w_T2.fqn == FQN("__spy__::interp_dict[type, i32]")

    @only_interp
    def test_literal_interp_dict(self):
        mod = self.compile("""
        from __spy__ import interp_dict

        def foo() -> interp_dict[type, i32]:
            d = interp_dict[type, i32]()
            d[i32] = 1
            d[f64] = 2
            d[str] = 3
            return d
        """)
        w_dict = mod.foo(unwrap=False)
        assert len(w_dict.items_w) == 3
        i32_key = B.w_i32.spy_key(self.vm)
        f64_key = B.w_f64.spy_key(self.vm)
        str_key = B.w_str.spy_key(self.vm)
        _, w_val1 = w_dict.items_w[i32_key]
        _, w_val2 = w_dict.items_w[f64_key]
        _, w_val3 = w_dict.items_w[str_key]
        assert self.vm.unwrap(w_val1) == 1
        assert self.vm.unwrap(w_val2) == 2
        assert self.vm.unwrap(w_val3) == 3

    @only_interp
    def test_generalize_literal(self):
        mod = self.compile("""
        from __spy__ import interp_dict

        def foo() -> type:
            d = interp_dict[type, i32]()
            d[i32] = 1
            d[f64] = 2
            return STATIC_TYPE(d)

        def bar() -> type:
            d = interp_dict[type, type]()
            d[i32] = i32
            d[f64] = f64
            return STATIC_TYPE(d)
        """)
        w_t1 = mod.foo(unwrap=False)
        assert isinstance(w_t1, W_Type)
        assert w_t1.fqn == FQN("__spy__::interp_dict[type, i32]")

        w_t2 = mod.bar(unwrap=False)
        assert isinstance(w_t2, W_Type)
        assert w_t2.fqn == FQN("__spy__::interp_dict[type, type]")

    @only_interp
    def test_empty_dict_to_interp_dict(self):
        src = """
        from __spy__ import interp_dict

        def foo() -> interp_dict[type, i32]:
            return {}
        """
        mod = self.compile(src)
        res = mod.foo()
        assert res == {}

    def test_empty_dict_to_stdlib_dict(self):
        import pytest

        pytest.skip("Empty dict conversion for stdlib dict not fully implemented yet")
        src = """
        from _dict import dict

        def foo() -> dict[i32, i32]:
            d: dict[i32, i32] = {}
            return d
        """
        mod = self.compile(src)
        res = mod.foo()
        assert res == {}

    @only_interp
    def test_type_as_dict_key(self):
        src = """
        from __spy__ import interp_dict

        def test() -> i32:
            d: interp_dict[type, i32] = {}
            d[i32] = 10
            d[f64] = 20
            return d[i32] + d[f64]
        """
        mod = self.compile(src)
        assert mod.test() == 30

    @only_interp
    def test_type_as_dict_value(self):
        src = """
        from __spy__ import interp_dict

        def test() -> type:
            d: interp_dict[str, type] = {}
            d["int"] = i32
            d["float"] = f64
            return d["int"]
        """
        mod = self.compile(src)
        w_result = mod.test(unwrap=False)
        assert w_result is B.w_i32

    @only_interp
    def test_type_as_both_dict_key_and_value(self):
        src = """
        from __spy__ import interp_dict

        def test() -> type:
            d: interp_dict[type, type] = {}
            d[i32] = str
            d[f64] = bool
            d[str] = i32
            return d[i32]
        """
        mod = self.compile(src)
        w_result = mod.test(unwrap=False)
        assert w_result is B.w_str
