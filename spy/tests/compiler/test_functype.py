from spy.tests.support import CompilerTest, expect_errors, only_interp
from spy.vm.b import TYPES, B
from spy.vm.function import FuncParam, W_FuncType


class TestFuncType(CompilerTest):
    @only_interp
    def test_type_construction(self):
        # After compiling a @functype-decorated def, the named variable holds
        # the W_FuncType for that signature.
        mod = self.compile("""
        @functype
        def CB(a: i32, b: i32) -> i32:
            pass
        """)
        w_CB = mod.w_mod.getattr("CB")
        assert isinstance(w_CB, W_FuncType)
        assert w_CB.w_restype is B.w_i32
        assert [p.w_T for p in w_CB.params] == [B.w_i32, B.w_i32]
        assert w_CB.color == "red"
        assert w_CB.kind == "plain"
        # FQN puts params first, restype last
        assert str(w_CB.fqn) == "builtins::def[i32, i32, i32]"

    @only_interp
    def test_type_identical_to_red_def(self):
        # The W_FuncType from @functype must be the SAME interned object as a
        # directly constructed W_FuncType with the same signature — so passing
        # a matching red function where that type is expected works by identity.
        mod = self.compile("""
        @functype
        def CB(x: i32) -> i32:
            pass
        """)
        w_CB = mod.w_mod.getattr("CB")
        w_T_direct = W_FuncType.new(
            [FuncParam(B.w_i32, "simple")], B.w_i32, color="red", kind="plain"
        )
        assert w_CB is w_T_direct

    def test_functype_decorator(self):
        self.compile("""
        @functype
        def CB(x: i32, y: i32) -> i32:
            pass

        def apply(cb: CB, x: i32, y: i32) -> i32:
            return x + y

        def my_add(a: i32, b: i32) -> i32:
            return a + b

        def run() -> i32:
            return apply(my_add, 3, 4)
        """)

    def test_functype_at_call_site(self):
        mod = self.compile("""
        @functype
        def CB(x: i32, y: i32) -> i32:
            pass

        def apply(cb: CB, x: i32, y: i32) -> i32:
            return x + y

        def my_add(a: i32, b: i32) -> i32:
            return a + b

        def run() -> i32:
            return apply(my_add, 3, 4)
        """)
        assert mod.run() == 7

    def test_signature_mismatch_wrong_ret(self):
        src = """
        @functype
        def CB(x: i32) -> bool:
            pass

        def my_fn(x: i32) -> i32:
            return x

        def bad() -> CB:
            return my_fn
        """
        errors = expect_errors("mismatched types")
        self.compile_raises(src, "bad", errors)

    def test_signature_mismatch_wrong_argcount(self):
        src = """
        @functype
        def CB(x: i32, y: i32) -> i32:
            pass

        def my_fn(x: i32) -> i32:
            return x

        def bad() -> CB:
            return my_fn
        """
        errors = expect_errors("mismatched types")
        self.compile_raises(src, "bad", errors)

    def test_signature_mismatch_wrong_arg_type(self):
        src = """
        @functype
        def CB(x: f64) -> i32:
            pass

        def my_fn(x: i32) -> i32:
            return x

        def bad() -> CB:
            return my_fn
        """
        errors = expect_errors("mismatched types")
        self.compile_raises(src, "bad", errors)

    def test_blue_func_rejected(self):
        # A @blue function's functype has a different FQN than a red functype,
        # so passing it where a @functype type is expected fails with a type mismatch.
        src = """
        @functype
        def CB(x: i32) -> i32:
            pass

        @blue
        def my_fn(x: i32) -> i32:
            return x

        def get_cb() -> CB:
            return my_fn
        """
        errors = expect_errors("mismatched types")
        self.compile_raises(src, "get_cb", errors)

    def test_blue_factory(self):
        # A @blue function can generate a red callback that captures compile-time
        # constants. After redshifting, captures are inlined so each becomes a
        # standalone C symbol.
        self.compile("""
        @functype
        def CB(x: i32) -> i32:
            pass

        @blue
        def make_adder(n: i32) -> CB:
            def adder(x: i32) -> i32:
                return x + n
            return adder

        add5: CB = make_adder(5)
        add10: CB = make_adder(10)
        """)
