from spy.tests.support import CompilerTest, expect_errors, only_interp
from spy.vm.b import B, TYPES
from spy.vm.modules.unsafe import UNSAFE
from spy.vm.modules.unsafe.funcptr import W_CFuncPtrType


class TestCFuncPtr(CompilerTest):
    @only_interp
    def test_type_construction(self):
        w_T = self.vm.fast_call(UNSAFE.w_c_func_ptr, [B.w_bool, B.w_i32, B.w_i32])
        assert isinstance(w_T, W_CFuncPtrType)
        assert w_T.w_restype is B.w_bool
        assert w_T.w_argtypes_w == [B.w_i32, B.w_i32]
        assert str(w_T.fqn) == "unsafe::c_func_ptr[bool, i32, i32]"
        assert repr(w_T) == "<spy type 'unsafe::c_func_ptr[bool, i32, i32]'>"

    @only_interp
    def test_type_construction_no_args(self):
        # c_func_ptr[void] — a callback with no arguments and no return value
        w_T = self.vm.fast_call(UNSAFE.w_c_func_ptr, [TYPES.w_NoneType])
        assert isinstance(w_T, W_CFuncPtrType)
        assert w_T.w_restype is TYPES.w_NoneType
        assert w_T.w_argtypes_w == []

    @only_interp
    def test_type_cached(self):
        # same parameters must produce the same type object (via blue cache)
        w_T1 = self.vm.fast_call(UNSAFE.w_c_func_ptr, [B.w_bool, B.w_i32])
        w_T2 = self.vm.fast_call(UNSAFE.w_c_func_ptr, [B.w_bool, B.w_i32])
        assert w_T1 is w_T2

    @only_interp
    def test_type_interned_across_constructors(self):
        # from_signature and w_c_func_ptr must return the same object so that
        # types declared in Python modules (like mymod) are identical to types
        # constructed from SPy source code.
        from spy.fqn import FQN
        w_T_via_spy = self.vm.fast_call(UNSAFE.w_c_func_ptr, [B.w_i32, B.w_i32])
        fqn = FQN("unsafe").join("c_func_ptr", [B.w_i32.fqn, B.w_i32.fqn])
        w_T_direct = W_CFuncPtrType.from_signature(fqn, B.w_i32, [B.w_i32])
        assert w_T_via_spy is w_T_direct

    def test_convert_from_matching_func(self):
        self.compile("""
        from unsafe import c_func_ptr

        def add(a: i32, b: i32) -> i32:
            return a + b

        CB = c_func_ptr[i32, i32, i32]

        def get_cb() -> CB:
            return add
        """)

    def test_convert_at_call_site(self):
        # c_func_ptr typed parameter receiving a SPy function directly
        mod = self.compile("""
        from unsafe import c_func_ptr

        CB = c_func_ptr[i32, i32, i32]

        def apply(cb: CB, x: i32, y: i32) -> i32:
            # At the interp level, a c_func_ptr const is the underlying W_Func,
            # so this acts as a direct call.
            return x + y

        def my_add(a: i32, b: i32) -> i32:
            return a + b

        def run() -> i32:
            return apply(my_add, 3, 4)
        """)
        assert mod.run() == 7

    def test_signature_mismatch_wrong_ret(self):
        src = """
        from unsafe import c_func_ptr

        CB = c_func_ptr[bool, i32]

        def my_fn(x: i32) -> i32:
            return x

        def bad() -> CB:
            return my_fn
        """
        errors = expect_errors("mismatched types")
        self.compile_raises(src, "bad", errors)

    def test_signature_mismatch_wrong_argcount(self):
        src = """
        from unsafe import c_func_ptr

        CB = c_func_ptr[i32, i32, i32]

        def my_fn(x: i32) -> i32:
            return x

        def bad() -> CB:
            return my_fn
        """
        errors = expect_errors("mismatched types")
        self.compile_raises(src, "bad", errors)

    def test_signature_mismatch_wrong_arg_type(self):
        src = """
        from unsafe import c_func_ptr

        CB = c_func_ptr[i32, f64]

        def my_fn(x: i32) -> i32:
            return x

        def bad() -> CB:
            return my_fn
        """
        errors = expect_errors("mismatched types")
        self.compile_raises(src, "bad", errors)

    def test_c_callback_decorator_valid(self):
        self.compile("""
        from unsafe import c_callback, c_func_ptr

        @c_callback
        def my_fn(x: i32) -> i32:
            return x + 1

        CB = c_func_ptr[i32, i32]

        def get_cb() -> CB:
            return my_fn
        """)

    def test_c_callback_rejects_blue_func(self):
        errors = expect_errors(
            "@c_callback cannot be applied to @blue functions",
            ("this is not a red function", "def my_fn(x: i32) -> i32"),
        )
        with errors:
            self.compile("""
            from unsafe import c_callback

            @c_callback
            @blue
            def my_fn(x: i32) -> i32:
                return x + 1
            """)

    def test_c_callback_blue_factory(self):
        # A @blue function can generate a red callback that captures compile-time
        # constants. After redshifting all captures are inlined, so the function
        # compiles to a standalone C symbol.
        self.compile("""
        from unsafe import c_callback, c_func_ptr

        CB = c_func_ptr[i32, i32]

        @blue
        def make_adder(n: i32) -> CB:
            @c_callback
            def adder(x: i32) -> i32:
                return x + n
            return adder

        add5: CB = make_adder(5)
        add10: CB = make_adder(10)
        """)

    def test_convert_rejects_blue_func(self):
        src = """
        from unsafe import c_func_ptr

        CB = c_func_ptr[i32, i32]

        @blue
        def my_fn(x: i32) -> i32:
            return x

        def get_cb() -> CB:
            return my_fn
        """
        errors = expect_errors(
            "c_func_ptr conversion requires a red (non-@blue) function",
            ("this is not a red function", "def my_fn(x: i32) -> i32"),
        )
        self.compile_raises(src, "get_cb", errors)
