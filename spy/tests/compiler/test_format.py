from spy.errors import SPyError
from spy.tests.support import CompilerTest, no_C
from spy.vm.builtin import builtin_method
from spy.vm.registry import ModuleRegistry
from spy.vm.str import W_Str
from spy.vm.vm import SPyVM
from spy.vm.w import W_Object


@no_C
class TestFormat(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def test_simple(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry("ext")

        @EXT.builtin_type("MyClass")
        class W_MyClass(W_Object):
            """A custom class which implements __format__ as func"""

            def __init__(self, w_prefix: W_Str) -> None:
                self.w_prefix = w_prefix

            @builtin_method("__new__")
            @staticmethod
            def w_new(vm: "SPyVM", w_prefix: W_Str) -> "W_MyClass":
                return W_MyClass(w_prefix)

            @builtin_method("__format__")
            @staticmethod
            def w_format(vm: "SPyVM", w_self: "W_MyClass", w_spec: W_Str) -> W_Str:
                prefix = vm.unwrap_str(w_self.w_prefix)
                spec = vm.unwrap_str(w_spec)
                return vm.wrap(f"{prefix}<{spec}>")

        # ========== /EXT module for this test =========
        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import MyClass

        def with_spec(prefix: str, spec: str) -> str:
            obj = MyClass(prefix)
            return format(obj, spec)

        def default_spec(prefix: str) -> str:
            obj = MyClass(prefix)
            return format(obj)
        """)
        assert mod.with_spec("x", "") == "x<>"
        assert mod.with_spec("x", "d") == "x<d>"
        assert mod.with_spec("hello", "!") == "hello<!>"
        assert mod.default_spec("hello") == "hello<>"

    def test_fallback_to_str(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry("ext")

        @EXT.builtin_type("MyClass")
        class W_MyClass(W_Object):
            def __init__(self, w_s: W_Str) -> None:
                self.w_s = w_s

            @builtin_method("__new__")
            @staticmethod
            def w_new(vm: "SPyVM", w_s: W_Str) -> "W_MyClass":
                return W_MyClass(w_s)

            @builtin_method("__str__")
            @staticmethod
            def w_str(vm: "SPyVM", w_self: "W_MyClass") -> W_Str:
                s = vm.unwrap_str(w_self.w_s)
                return vm.wrap(f"<str>{s}")

        # ========== /EXT module for this test =========
        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import MyClass

        def foo(s: str) -> str:
            obj = MyClass(s)
            return format(obj)

        def bar(s: str) -> str:
            obj = MyClass(s)
            return format(obj, "x")
        """)
        assert mod.foo("hello") == "<str>hello"
        with SPyError.raises(
            "W_TypeError",
            match="unsupported format string passed to `ext::MyClass`.__format__",
        ):
            mod.bar("hello")
