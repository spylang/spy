from spy.errors import SPyError
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

    def test_FormatSpec(self):
        mod = self.compile("""
        from _format import FormatSpec

        def parse(spec: str) -> FormatSpec:
            return FormatSpec.parse(spec)
        """)
        # FormatSpec ==> (fill, align, width, precision, type)
        assert mod.parse("") == ("", "", -1, -1, "")

        # type only
        assert mod.parse("s") == ("", "", -1, -1, "s")

        # width only
        assert mod.parse("5") == ("", "", 5, -1, "")
        assert mod.parse("42") == ("", "", 42, -1, "")

        # align only, and fill+align
        assert mod.parse("<5") == ("", "<", 5, -1, "")
        assert mod.parse("x>6") == ("x", ">", 6, -1, "")

        # the '0' flag sets the fill, unless one was given explicitly
        assert mod.parse("05") == ("0", "", 5, -1, "")
        assert mod.parse("<05") == ("0", "<", 5, -1, "")
        assert mod.parse("0>5") == ("0", ">", 5, -1, "")

        # precision
        assert mod.parse(".3") == ("", "", -1, 3, "")
        assert mod.parse(".0") == ("", "", -1, 0, "")

        # everything at once
        assert mod.parse("*^12.3s") == ("*", "^", 12, 3, "s")

        with SPyError.raises("W_ValueError", match="missing precision"):
            mod.parse(".")

        # like CPython, a '.' not followed by digits is a missing precision
        with SPyError.raises("W_ValueError", match="missing precision"):
            mod.parse("5..2")

        with SPyError.raises("W_ValueError", match="invalid format spec"):
            mod.parse("5s3")

    def test_i32(self):
        mod = self.compile("""
        def fmt(x: i32, spec: str) -> str:
            return format(x, spec)

        """)
        assert mod.fmt(42, "d") == "42"
        assert mod.fmt(-5, "d") == "-5"
        assert mod.fmt(0, "") == "0"

    def test_float(self):
        mod = self.compile("""
        def fmt_f64(x: f64, spec: str) -> str:
            return format(x, spec)

        def fmt_f32(x: f32, spec: str) -> str:
            return format(x, spec)
        """)
        assert mod.fmt_f64(12.3, "") == "12.3"
        assert mod.fmt_f32(12.3, "") == "12.3"
        with SPyError.raises(
            "W_WIP", match="f64.__format__: format spec not supported"
        ):
            mod.fmt_f64(12.3, ".2f")
        with SPyError.raises(
            "W_WIP", match="f32.__format__: format spec not supported"
        ):
            mod.fmt_f32(12.3, ".2f")

    def test_str(self):
        mod = self.compile("""
        def fmt(s: str, spec: str) -> str:
            return format(s, spec)
        """)
        # no formatting
        assert mod.fmt("hi", "") == "hi"
        assert mod.fmt("hi", "s") == "hi"

        # width only: default align is '<'
        assert mod.fmt("hi", "5") == "hi   "
        assert mod.fmt("", "3") == "   "
        # width smaller than the string: no padding, no truncation
        assert mod.fmt("hello", "1") == "hello"

        # explicit align, default fill
        assert mod.fmt("hi", "<5") == "hi   "
        assert mod.fmt("hi", ">5") == "   hi"
        # '^' with an even and an odd amount of padding (extra char goes right)
        assert mod.fmt("hi", "^6") == "  hi  "
        assert mod.fmt("hi", "^7") == "  hi   "

        # explicit fill
        assert mod.fmt("hi", "x<4") == "hixx"
        assert mod.fmt("hi", "->6") == "----hi"
        assert mod.fmt("hi", "*^7") == "**hi***"

        # the '0' flag sets the fill, with and without an explicit align
        assert mod.fmt("hi", "05") == "hi000"
        assert mod.fmt("hi", "<05") == "hi000"
        # ... but an explicit fill wins
        assert mod.fmt("hi", "x>05") == "xxxhi"

        # precision truncates; it is a no-op if the string is shorter
        assert mod.fmt("world", ".3") == "wor"
        assert mod.fmt("hi", ".3") == "hi"
        assert mod.fmt("world", ".0") == ""

        # precision and width together: truncate first, then pad
        assert mod.fmt("world", "8.3") == "wor     "
        assert mod.fmt("world", ">8.3") == "     wor"
        assert mod.fmt("world", "^9.2") == "   wo    "

        with SPyError.raises("W_ValueError", match="invalid format spec for str"):
            mod.fmt("hi", "d")
