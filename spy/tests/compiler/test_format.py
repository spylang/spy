from spy.tests.support import CompilerTest, expect_errors


class TestFormat(CompilerTest):
    """
    This test the basics of the `format()` builtin, how it calls `__format__` and
    how it fallbacks to `__str__`.

    The actual implementation of `__format__` for most types lives in
    `stdlib/_format.spy` and it's thus tested in `tests/stdlib/test__format.py`
    """

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
