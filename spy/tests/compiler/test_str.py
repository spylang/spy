#-*- encoding: utf-8 -*-

import re
from spy.errors import SPyError
from spy.tests.support import CompilerTest, skip_backends

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

    def test_object_str_blue(self):
        src = """
        def str_blue() -> str:
            return str(i32)
        """
        mod = self.compile(src)
        assert mod.str_blue() == "<spy type 'i32'>"

    @skip_backends('C', reason='`type` type not supported')
    def test_object_str_red(self):
        src = """
        def str_red_type() -> str:
            t: type = i32   # note, this is a red variable
            return str(t)
        """
        mod = self.compile(src)
        s = mod.str_red_type()
        assert re.fullmatch(r"<spy `type` object at 0x.+>", s)

    def test_str_numbers(self):
        # NOTE: float2str produces slightly different results in Python vs C
        # backend: e.g. str(0.0) == '0' in Pytohn, '0.0' in the C backend.
        # Eventually, we want to port the formatting code from CPython, but
        # for now we just allow both results and keep the C backend simple.
        mod = self.compile("""
        def str_i32(x: i32) -> str:
            return str(x)

        def str_i8(x: i8) -> str:
            return str(x)

        def str_u8(x: u8) -> str:
            return str(x)

        def str_f64(x: f64) -> str:
            return str(x)

        def str_bool(x: bool) -> str:
            return str(x)
        """)
        assert mod.str_i32(-10) == '-10'
        assert mod.str_i32(123) == '123'
        assert mod.str_i8(-10) == '-10'
        assert mod.str_i8(127) == '127'
        assert mod.str_i8(-128) == '-128'
        assert mod.str_u8(0) == '0'
        assert mod.str_u8(255) == '255'
        assert mod.str_f64(-10.5) == '-10.5'
        assert mod.str_f64(0.0) in ('0', '0.0')
        assert mod.str_f64(3.14) == '3.14'
        assert mod.str_f64(123.456) == '123.456'
        assert mod.str_bool(True) == 'True'
        assert mod.str_bool(False) == 'False'

    def test_repr_blue(self):
        src = """
        def repr_blue() -> str:
            return repr(i32)
        """
        mod = self.compile(src)
        assert mod.repr_blue() == "<spy type 'i32'>"

    @skip_backends('C', reason='`type` type not supported')
    def test_repr_red(self):
        src = """
        def repr_red_type() -> str:
            t: type = i32   # note, this is a red variable
            return repr(t)
        """
        mod = self.compile(src)
        s = mod.repr_red_type()
        assert re.fullmatch(r"<spy `type` object at 0x.+>", s)

    def test_str_fallback_to_repr(self):
        # str() should fallback to repr() for types without custom __str__
        src = """
        def str_blue() -> str:
            return str(i32)

        def repr_blue() -> str:
            return repr(i32)
        """
        mod = self.compile(src)
        assert mod.str_blue() == mod.repr_blue()

    def test_str_none(self):
        src = """
        def foo() -> str:
            return str(None)
        """
        mod = self.compile(src)
        assert mod.foo() == 'None'

    def test_str_not_implemented(self):
        src = """
        def foo() -> str:
            return str(NotImplemented)
        """
        mod = self.compile(src)
        assert mod.foo() == 'NotImplemented'
