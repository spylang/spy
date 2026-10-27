from spy.fqn import FQN
from spy.tests.support import CompilerTest, expect_errors, no_C, only_interp
from spy.vm.b import B
from spy.vm.object import W_Type


class TestList(CompilerTest):
    """
    These are only few of the tests about list, mostly to check that:

      1. list[T] does the right thing

      2. the list literal syntax "[a, b, c, ...]" works

    The actual behavior of list objects is tested by stdlib/test__list.py and
    test_interp_list.py
    """

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

    @only_interp
    def test_list_MetaArg_identity(self):
        # This test is needed because of what likely is a design issue of W_MetaArg,
        # which we should probably fix.
        #
        # W_MetaArg compares by VALUE, so m_a and m_b are equal.
        #
        # SPy's blue/red machinery is built on the assumption that value types don't
        # have identity: if they are equal, they can be used interchangeably; because of
        # that a naive implementation of eval_expr_List would _push() m_a twice (which
        # is fine since it's equal to m_b).
        #
        # HOWEVER, for the specific case of W_MetaArg, identity matters, because it's
        # what we use to map OpSpec-to-OpImpl args. So, it's important that the
        # resulting list contains [m_a, m_b] instead of [m_a, m_a].
        src = """
        from __spy__ import interp_list
        from operator import MetaArg

        # NOTE: list[MetaArg] is interp_list[MetaArg], so both functions return the same
        # type in reality. The big difference is whether they use a list literal or a
        # direct ctor call

        def with_list_literal() -> list[MetaArg]:
            m_a: MetaArg = i32
            m_b: MetaArg = i32
            # m_a and m_b are EQUAL, but not identicaly
            assert m_a == m_b
            return [m_a, m_b]

        def with_interp_list_ctor() -> interp_list[MetaArg]:
            m_a: MetaArg = i32
            m_b: MetaArg = i32
            # m_a and m_b are EQUAL, but not identicaly
            assert m_a == m_b
            return interp_list[MetaArg](m_a, m_b)
        """
        mod = self.compile(src)
        w_lst1 = mod.with_list_literal(unwrap=False)
        assert len(w_lst1.items_w) == 2
        wam_a, wam_b = w_lst1.items_w
        assert wam_a is not wam_b
        #
        w_lst2 = mod.with_interp_list_ctor(unwrap=False)
        assert len(w_lst2.items_w) == 2
        wam_a, wam_b = w_lst2.items_w
        assert wam_a is not wam_b

    @only_interp
    def test_interp_list_MetaArg_ctor(self):
        # this is another problem caused by the W_MetaArg identity design issue.
        # This is what happened before PR 741:
        #   1. the 1st call to `op.CALL(interp_list[MetaArg], ...)` returns an OpImpl;
        #      the OpImpl gets a "meta-MetaArg" with blueval==m_a
        #   2. the 2nd call to `op.CALL(...)` checks the bluecache
        #   3. since m_a and m_b are EQUAL, we hit the bluecache and return the cached OpImpl
        #   4. the cached opimpl invokes the ctor with m_a AGAIN
        #
        # This is perfectly fine with "real" value types, because they don't have an
        # applevel identity and are they are indistinguishable. But W_MetaArg is
        # "special" (and probably buggy in this sense) and thus the interp-level
        # identity matters.
        #
        # The solution is to add a special case interp_list[MetaArg]
        src = """
        from __spy__ import interp_list, interp_tuple
        from operator import MetaArg

        def foo() -> interp_tuple:
            m_a: MetaArg = i32  # implicit conv from type to MetaArg
            m_b: MetaArg = i32
            # m_a and m_b are EQUAL, but not identicaly
            assert m_a == m_b
            la = interp_list[MetaArg](m_a)
            lb = interp_list[MetaArg](m_b)
            return interp_tuple(la, lb)
        """
        mod = self.compile(src)
        w_tup = mod.foo(unwrap=False)
        w_la, w_lb = w_tup.items_w
        assert w_la is not w_lb
        wam_a = w_la.items_w[0]
        wam_b = w_lb.items_w[0]
        assert wam_a is not wam_b

    @no_C
    def test_empty_list_singleton(self):
        src = """
        import __spy__

        def get_empty() -> __spy__.EmptyListType:
            return []
        """
        mod = self.compile(src)
        w_a = mod.get_empty(unwrap=False)
        w_b = mod.get_empty(unwrap=False)
        assert w_a is w_b

    @no_C
    def test_empty_list_to_interp_list(self):
        src = """
        def foo() -> list[object]:
            return []
        """
        mod = self.compile(src)
        res = mod.foo()
        assert res == []

    def test_empty_list_to_stdlib_list(self):
        src = """
        def foo() -> list[i32]:
            return []
        """
        mod = self.compile(src)
        res = mod.foo()
        assert res == []

    def test_converted_empty_list_can_mutate(self):
        src = """
        def foo() -> list[i32]:
            l: list[i32] = []
            l.append(1)
            l.append(2)
            l.append(3)
            return l
        """
        mod = self.compile(src)
        res = mod.foo()
        assert res == [1, 2, 3]

    def test_bare_empty_list_cannot_mutate(self):
        src = """
        def foo() -> list[i32]:
            l = []
            l.append(1)
            return l
        """
        errors = expect_errors(
            "cannot mutate an untyped empty list",
            ("this is untyped", "l"),
            ("help: use an explicit type: `l: list[T] = []`", "l"),
        )
        self.compile_raises(src, "foo", errors)

    def test_list_of_structs_init(self):
        src = """
        @struct
        class Point:
            x: i32
            y: i32

        def foo() -> i32:
            lst: list[Point] = [Point(10, 2)]
            return lst[0].x + lst[0].y
        """
        mod = self.compile(src)
        res = mod.foo()
        assert res == 12

    def test_struct_with_list_field(self):
        # NOTE: what this is actually testing is that in the C backend we do a
        # topological sort of structdefs, i.e. that we emit list[i32] before Item. See
        # also test_importing.test_structdefs_toposort and CBackend.split_fqns()
        src = """
        @struct
        class Item:
            values: list[i32]

        def foo() -> i32:
            item = Item.__make__([1, 2, 3])
            return item.values[1]
        """
        mod = self.compile(src)
        assert mod.foo() == 2
