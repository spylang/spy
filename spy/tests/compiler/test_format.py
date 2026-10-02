from spy.tests.support import CompilerTest, expect_errors


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
        """)
        assert mod.foo("hello") == "<str>hello"

    def test_fallback_non_empty_spec(self):
        src = """
        @struct
        class MyClass:
            s: str

            def __str__(self) -> str:
                return f"<str>{self.s}"

        def bar() -> str:
            obj = MyClass("hello")
            return format(obj, "x")
        """
        errors = expect_errors(
            "unsupported format string passed to `test::MyClass`.__format__",
            ("this is the format spec", '"x"'),
        )
        self.compile_raises(src, "bar", errors)

    def test_fallback_red_spec(self):
        src = """
        from __spy__ import as_red

        @struct
        class MyClass:
            s: str

        def foo() -> str:
            obj = MyClass("hello")
            return format(obj, as_red("x"))
        """
        errors = expect_errors(
            "expected blue argument",
            ("this is red", 'as_red("x")'),
        )
        self.compile_raises(src, "foo", errors)

    def test_i32(self):
        mod = self.compile("""
        def fmt(x: i32, spec: str) -> str:
            return format(x, spec)

        """)
        assert mod.fmt(42, "d") == "42"
        assert mod.fmt(-5, "d") == "-5"
        assert mod.fmt(0, "") == "0"
