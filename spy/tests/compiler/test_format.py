from spy.errors import SPyError
from spy.tests.support import CompilerTest, no_C
from spy.vm.builtin import builtin_method
from spy.vm.registry import ModuleRegistry
from spy.vm.str import W_Str
from spy.vm.vm import SPyVM
from spy.vm.w import W_Object


class TestFormat(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def test_simple(self):
        mod = self.compile("""
        @struct
        class MyClass:
            prefix: str

            def __format__(self, spec: str) -> str:
                return f"{self.prefix}<{spec}>"

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

    @no_C
    def test_fallback_to_str(self):
        mod = self.compile("""
        @struct
        class MyClass:
            s: str

            def __str__(self) -> str:
                return f"<str>{self.s}"

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
            match="unsupported format string passed to `test::MyClass`.__format__",
        ):
            mod.bar("hello")
