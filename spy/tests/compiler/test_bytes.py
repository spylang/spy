from spy.errors import SPyError
from spy.tests.support import CompilerTest, only_interp


class TestBytes(CompilerTest):
    def test_literal(self):
        mod = self.compile("""
        def foo() -> bytes:
            return b'hello'

        def bar() -> bytes:
            return b''
        """)
        assert mod.foo() == b"hello"
        assert mod.bar() == b""

    def test_len(self):
        mod = self.compile("""
        def foo() -> i32:
            return len(b'abc')
        """)
        assert mod.foo() == 3

    def test_add(self):
        mod = self.compile("""
        def foo() -> bytes:
            a: bytes = b'hello '
            b: bytes = b'world'
            return a + b
        """)
        assert mod.foo() == b"hello world"

    def test_multiply(self):
        mod = self.compile("""
        def foo() -> bytes:
            a: bytes = b'ab'
            return a * 3
        """)
        assert mod.foo() == b"ababab"

    def test_getitem(self):
        mod = self.compile("""
        def foo(b: bytes, i: i32) -> i32:
            return b[i]
        """)
        assert mod.foo(b"ABCDE", 0) == ord("A")
        assert mod.foo(b"ABCDE", 4) == ord("E")

    def test_getitem_negative(self):
        mod = self.compile("""
        def foo(b: bytes, i: i32) -> i32:
            return b[i]
        """)
        assert mod.foo(b"ABC", -1) == ord("C")

    def test_eq_ne(self):
        mod = self.compile("""
        def eq(a: bytes, b: bytes) -> bool:
            return a == b

        def ne(a: bytes, b: bytes) -> bool:
            return a != b
        """)
        assert mod.eq(b"abc", b"abc") is True
        assert mod.eq(b"abc", b"aaa") is False
        assert mod.ne(b"abc", b"abc") is False
        assert mod.ne(b"abc", b"aaa") is True

    def test_repr_str(self):
        mod = self.compile("""
        def b_repr(b: bytes) -> str:
            return repr(b)

        def b_str(b: bytes) -> str:
            return str(b)
        """)
        # printable ASCII: no escaping
        assert mod.b_repr(b"abc") == "b'abc'"
        # backslash
        assert mod.b_repr(b"a\\b") == "b'a\\\\b'"
        # single quote
        assert mod.b_repr(b"a'b") == "b'a\\'b'"
        # \n \r \t shortcuts
        assert mod.b_repr(b"\n") == "b'\\n'"
        assert mod.b_repr(b"\r") == "b'\\r'"
        assert mod.b_repr(b"\t") == "b'\\t'"
        # control char below space (not \n/\r/\t) -> \xNN
        assert mod.b_repr(b"\x00") == "b'\\x00'"
        assert mod.b_repr(b"\x1f") == "b'\\x1f'"
        # byte above tilde -> \xNN, exercising both hex digit branches (>=10 and <10)
        assert mod.b_repr(b"\x7f") == "b'\\x7f'"
        assert mod.b_repr(b"\xff") == "b'\\xff'"
        assert mod.b_repr(b"\xa0") == "b'\\xa0'"
        # empty
        assert mod.b_repr(b"") == "b''"
        # mixed
        assert mod.b_repr(b"a\x00b") == "b'a\\x00b'"
        #
        # str() just calls repr()
        assert mod.b_str(b"abc") == "b'abc'"

    def test_hash_stable(self):
        mod = self.compile("""
        def foo() -> i32:
            return hash(b'abc')
        """)
        result = mod.foo()
        assert result != 0
        assert result == mod.foo()

    def test_decode(self):
        src = """
        def decode(b: bytes) -> str:
            return b.decode("utf-8")
        """
        mod = self.compile(src)
        assert mod.decode(b"hello") == "hello"
        assert mod.decode(b"") == ""
        assert mod.decode("àèìòù".encode("utf-8")) == "àèìòù"

    def test_decode_unsupported(self):
        src = """
        def decode(b: bytes, enc: str) -> str:
            return b.decode(enc)
        """
        mod = self.compile(src)
        with SPyError.raises("W_ValueError"):
            mod.decode(b"x", "ascii")

    def test_encode_decode_roundtrip(self):
        src = """
        def roundtrip(s: str) -> str:
            return s.encode("utf-8").decode("utf-8")
        """
        mod = self.compile(src)
        assert mod.roundtrip("hello world") == "hello world"
        assert mod.roundtrip("àèìòù") == "àèìòù"
