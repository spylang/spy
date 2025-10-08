import pytest

from spy.tests.support import CompilerTest, expect_errors, no_C
from spy.vm.builtin import builtin_method
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.primitive import W_I32
from spy.vm.registry import ModuleRegistry
from spy.vm.vm import SPyVM
from spy.vm.w import W_Object


@no_C
class TestOpSpec(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def test_opspec_type_mismatch(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry("ext")

        @EXT.builtin_type("MyClass")
        class W_MyClass(W_Object):

            @builtin_method("__new__")
            @staticmethod
            def w_new(vm: "SPyVM") -> "W_MyClass":
                return W_MyClass()

            @builtin_method("__getitem__", color="blue", kind="metafunc")
            @staticmethod
            def w_GETITEM(vm: "SPyVM", wam_obj: W_MetaArg,
                          wam_i: W_MetaArg) -> W_OpSpec:
                @vm.register_builtin_func("ext")
                def w_getitem(vm: "SPyVM", w_obj: W_MyClass,
                              w_i: W_I32) -> W_I32:
                    return w_i
                return W_OpSpec(w_getitem)
        # ========== /EXT module for this test =========

        self.vm.make_module(EXT)
        src = """
        from ext import MyClass

        def foo() -> i32:
            obj = MyClass()
            return obj['hello']
        """
        errors = expect_errors(
            "mismatched types",
            ("expected `i32`, got `str`", "'hello'"),
        )
        self.compile_raises(src, "foo", errors)

    def test_opspec_wrong_argcount(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry("ext")

        @EXT.builtin_type("MyClass")
        class W_MyClass(W_Object):

            @builtin_method("__new__")
            @staticmethod
            def w_new(vm: "SPyVM") -> "W_MyClass":
                return W_MyClass()

            @builtin_method("__getitem__", color="blue", kind="metafunc")
            @staticmethod
            def w_GETITEM(vm: "SPyVM", wam_obj: W_MetaArg,
                          wam_i: W_MetaArg) -> W_OpSpec:
                @vm.register_builtin_func("ext")
                def w_getitem(vm: "SPyVM", w_obj: W_MyClass) -> W_I32:
                    return vm.wrap(42)  # type: ignore
                return W_OpSpec(w_getitem)
        # ========== /EXT module for this test =========

        self.vm.make_module(EXT)
        src = """
        from ext import MyClass

        def foo() -> i32:
            obj = MyClass()
            return obj[0]
        """
        errors = expect_errors(
            "this function takes 1 argument but 2 arguments were supplied",
        )
        self.compile_raises(src, "foo", errors)

    def test_complex_OpSpec(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry("ext")

        @EXT.builtin_type("MyClass")
        class W_MyClass(W_Object):

            def __init__(self, w_x: W_I32):
                self.w_x = w_x

            @builtin_method("__new__")
            @staticmethod
            def w_new(vm: "SPyVM", w_x: W_I32) -> "W_MyClass":
                return W_MyClass(w_x)

            @builtin_method("__getitem__", color="blue", kind="metafunc")
            @staticmethod
            def w_GETITEM(vm: "SPyVM", wam_obj: W_MetaArg,
                          wam_i: W_MetaArg) -> W_OpSpec:
                assert isinstance(wam_obj, W_MetaArg)
                assert isinstance(wam_i, W_MetaArg)
                # NOTE we are reversing the two arguments
                return W_OpSpec(EXT.w_sum, [wam_i, wam_obj])

        @EXT.builtin_func
        def w_sum(vm: "SPyVM", w_i: W_I32, w_obj: W_MyClass) -> W_I32:
            assert isinstance(w_i, W_I32)
            assert isinstance(w_obj, W_MyClass)
            a = vm.unwrap_i32(w_i)
            b = vm.unwrap_i32(w_obj.w_x)
            return vm.wrap(a+b)
        # ========== /EXT module for this test =========

        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import MyClass

        def foo(a: i32, b: i32) -> i32:
            obj = MyClass(a)
            return obj[b]
        """)
        assert mod.foo(10, 20) == 30

    def test_OpSpec_new(self):
        if self.backend == "doppler":
            pytest.skip("OpSpec becomes blue? FIXME")

        mod = self.compile("""
        from operator import OpSpec

        def bar() -> None:
            pass

        def foo() -> dynamic:
            return OpSpec(bar)
        """)
        w_opspec = mod.foo(unwrap=False)
        assert isinstance(w_opspec, W_OpSpec)
        assert w_opspec._w_func is mod.bar.w_func

    def test_opspec_const(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry("ext")

        @EXT.builtin_type("MyClass")
        class W_MyClass(W_Object):

            @builtin_method("__new__")
            @staticmethod
            def w_new(vm: "SPyVM") -> "W_MyClass":
                return W_MyClass()

            @builtin_method("__getitem__", color="blue", kind="metafunc")
            @staticmethod
            def w_GETITEM(vm: "SPyVM", wam_obj: W_MetaArg,
                          wam_i: W_MetaArg) -> W_OpSpec:
                return W_OpSpec.const(vm.wrap(42))
        # ========== /EXT module for this test =========

        self.vm.make_module(EXT)
        src = """
        from ext import MyClass

        def foo() -> i32:
            obj = MyClass()
            return obj['hello']
        """
        mod = self.compile(src)
        assert mod.foo() == 42
