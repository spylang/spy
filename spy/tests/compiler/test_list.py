from spy.fqn import FQN
from spy.tests.support import CompilerTest, only_interp
from spy.vm.b import B
from spy.vm.object import W_Type


class TestList(CompilerTest):
    @only_interp
    def test_list_type(self):
        # by default we use _list.list, but for some itemtype we use interp_list
        src = """
        def list_i32() -> type:
            return list[i32]

        def list_type() -> type:
            return list[type]
        """
        mod = self.compile(src)
        w_T1 = mod.list_i32(unwrap=False)
        assert w_T1.fqn == FQN("_list::list[i32]::_ListImpl")
        assert w_T1.is_struct(self.vm)
        #
        w_T2 = mod.list_type(unwrap=False)
        assert w_T2.fqn == FQN("__spy__::interp_list[type]")

    def test_literal_stdlib(self):
        # list[i32] is implemented by stdlib/_list.spy
        mod = self.compile("""
        def foo() -> list[i32]:
            x = [1, 2, 3]
            return x
        """)
        x = mod.foo()
        assert x == [1, 2, 3]

    @only_interp
    def test_literal_interp_list(self):
        mod = self.compile("""
        def foo() -> list[type]:
            return [i32, f64, str]
        """)
        w_lst = mod.foo(unwrap=False)
        assert w_lst.items_w == [B.w_i32, B.w_f64, B.w_str]

    @only_interp
    def test_generalize_literal(self):
        mod = self.compile("""
        def foo() -> type:
            x = [i32, f64, str]
            return STATIC_TYPE(x)

        def bar() -> type:
            x = [i32, f64, 'hello']
            return STATIC_TYPE(x)
        """)
        w_t1 = mod.foo(unwrap=False)
        assert isinstance(w_t1, W_Type)
        assert w_t1.fqn == FQN("__spy__::interp_list[type]")
        w_t2 = mod.bar(unwrap=False)
        assert isinstance(w_t2, W_Type)
        assert w_t2.fqn == FQN("__spy__::interp_list[object]")

    @only_interp
    def test_list_MetaArg(self):
        src = """
        from operator import MetaArg

        def foo() -> list[MetaArg]:
            m_a: MetaArg = i32
            m_b: MetaArg = f64
            return [m_a, m_b]
        """
        mod = self.compile(src)
        w_lst = mod.foo(unwrap=False)
        w_T = self.vm.dynamic_type(w_lst)
        assert w_T.fqn == FQN("__spy__::interp_list[operator::MetaArg]")
        assert len(w_lst.items_w) == 2
        wam_a, wam_b = w_lst.items_w
        assert wam_a.w_static_T is B.w_i32
        assert wam_b.w_static_T is B.w_f64
