from spy.tests.support import CompilerTest, only_interp


class TestBytes(CompilerTest):
    def test_literal_empty(self):
        mod = self.compile("""
        def foo() -> bytes:
            return b''
        """)
        assert mod.foo() == b""

    def test_literal(self):
        mod = self.compile("""
        def foo() -> bytes:
            return b'hello'
        """)
        assert mod.foo() == b"hello"

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

    def test_eq_true(self):
        mod = self.compile("""
        def foo() -> bool:
            return b'abc' == b'abc'
        """)
        assert mod.foo() is True

    def test_eq_false(self):
        mod = self.compile("""
        def foo() -> bool:
            return b'abc' == b'abd'
        """)
        assert mod.foo() is False

    def test_ne(self):
        mod = self.compile("""
        def foo() -> bool:
            return b'abc' != b'abd'
        """)
        assert mod.foo() is True

    def test_repr(self):
        mod = self.compile("""
        def foo() -> str:
            return repr(b'a\\x00b')
        """)
        assert mod.foo() == "b'a\\x00b'"

    def test_hash_stable(self):
        mod = self.compile("""
        def foo() -> i32:
            return hash(b'abc')
        """)
        result = mod.foo()
        assert result != 0
        assert result == mod.foo()

    def test_bytes_argument(self):
        mod = self.compile("""
        def foo(b: bytes) -> bytes:
            return b + b'!'
        """)
        assert mod.foo(b"hello") == b"hello!"

    def test_BytesObject_roundtrip(self):
        mod = self.compile("""
        from _bytes import BytesObject

        def foo() -> i32:
            ll = BytesObject.from_bytes(b'hello')
            return ll.length
        """)
        assert mod.foo() == 5
