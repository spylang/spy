#-*- encoding: utf-8 -*-

from spy.errors import SPyError
from spy.tests.support import CompilerTest

class TestStr(CompilerTest):

    def test_literal(self):
        mod = self.compile(
        """
        def foo() -> str:
            return 'hello'
        """)
        assert mod.foo() == 'hello'

    def test_unicode_chars(self):
        mod = self.compile(
        """
        # -*- encoding: utf-8 -*-
        def foo() -> str:
            return 'hello àèìòù'
        """)
        assert mod.foo() == 'hello àèìòù'

    def test_add(self):
        mod = self.compile(
        """
        def foo() -> str:
            a: str = 'hello '
            b: str = 'world'
            return a + b
        """)
        assert mod.foo() == 'hello world'

    def test_multiply(self):
        mod = self.compile(
        """
        def foo() -> str:
            a: str = 'hello '
            return a * 3
        """)
        assert mod.foo() == 'hello hello hello '

    def test_str_argument(self):
        mod = self.compile(
        """
        def foo(a: str) -> str:
            return a + ' world'
        """)
        assert mod.foo('hello') == 'hello world'

    def test_getitem(self):
        mod = self.compile(
        """
        def foo(a: str, i: i32) -> str:
            return a[i]
        """)
        assert mod.foo('ABCDE', 0) == 'A'
        assert mod.foo('ABCDE', 1) == 'B'
        assert mod.foo('ABCDE', -1) == 'E'
        with SPyError.raises("W_IndexError", match="string index out of bound"):
            mod.foo('ABCDE', 5)
        with SPyError.raises("W_IndexError", match="string index out of bound"):
            mod.foo('ABCDE', -6)

    def test_compare(self):
        mod = self.compile(
        """
        def eq(a: str, b: str) -> bool:
            return a == b

        def ne(a: str, b: str) -> bool:
            return a != b
        """)
        assert mod.eq("aaa", "aaa")
        assert not mod.eq("aaa", "bbb")
        assert mod.ne("aaa", "bbb")
        assert not mod.ne("aaa", "aaa")

    def test_len(self):
        src = """
        def foo(s: str) -> i32:
            return len(s)
        """
        mod = self.compile(src)
        assert mod.foo("") == 0
        assert mod.foo("abc") == 3
        assert mod.foo("hello world") == 11
