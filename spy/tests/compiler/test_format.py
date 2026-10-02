from spy.tests.support import CompilerTest, no_C
from spy.vm.builtin import builtin_method
from spy.vm.registry import ModuleRegistry
from spy.vm.str import W_Str
from spy.vm.vm import SPyVM
from spy.vm.w import W_Object


@no_C
class TestFormat(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def test_format(self):
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
                return vm.wrap(prefix + "<" + spec + ">")

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
