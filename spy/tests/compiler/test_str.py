#-*- encoding: utf-8 -*-

import pytest
from spy.libspy import SPyPanicError
from spy.tests.support import CompilerTest, skip_backends, no_backend

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

    def test_add(self, legacy):
        mod = self.compile(
        """
        def foo() -> str:
            a: str = 'hello '
            b: str = 'world'
            return a + b
        """)
        assert mod.foo() == 'hello world'

    def test_multiply(self, legacy):
        mod = self.compile(
        """
        def foo() -> str:
            a: str = 'hello '
            return a * 3
        """)
        assert mod.foo() == 'hello hello hello '

    def test_str_argument(self, legacy):
        mod = self.compile(
        """
        def foo(a: str) -> str:
            return a + ' world'
        """)
        assert mod.foo('hello') == 'hello world'

    def test_getitem(self, legacy):
        mod = self.compile(
        """
        def foo(a: str, i: i32) -> str:
            return a[i]
        """)
        assert mod.foo('ABCDE', 0) == 'A'
        assert mod.foo('ABCDE', 1) == 'B'
        assert mod.foo('ABCDE', -1) == 'E'
        with pytest.raises(SPyPanicError, match="string index out of bound"):
            mod.foo('ABCDE', 5)
        with pytest.raises(SPyPanicError, match="string index out of bound"):
            mod.foo('ABCDE', -6)
