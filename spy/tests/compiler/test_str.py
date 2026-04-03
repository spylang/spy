import re

from spy.errors import SPyError
from spy.tests.support import CompilerTest, skip_backends


class TestStr(CompilerTest):
    def test_literal(self):
        mod = self.compile("""
        def foo() -> str:
            return 'hello'
        """)
        assert mod.foo() == "hello"

    def test_unicode_chars(self):
        mod = self.compile("""
        # -*- encoding: utf-8 -*-
        def foo() -> str:
            return 'hello àèìòù'
        """)
        assert mod.foo() == "hello àèìòù"

    def test_add(self):
        mod = self.compile("""
        def foo() -> str:
            a: str = 'hello '
            b: str = 'world'
            return a + b
        """)
        assert mod.foo() == "hello world"

    def test_multiply(self):
        mod = self.compile("""
        def foo() -> str:
            a: str = 'hello '
            return a * 3
        """)
        assert mod.foo() == "hello hello hello "

    def test_str_argument(self):
        mod = self.compile("""
        def foo(a: str) -> str:
            return a + ' world'
        """)
        assert mod.foo("hello") == "hello world"

    def test_str_functions_always_exported(self):
        # see the comment about --whole-archive in spy/build/config.py
        mod = self.compile("""
        def identity(s: str) -> str:
            return s
        """)
        assert mod.identity("hello") == "hello"

    def test_getitem(self):
        mod = self.compile("""
        def foo(a: str, i: i32) -> str:
            return a[i]
        """)
        assert mod.foo("ABCDE", 0) == "A"
        assert mod.foo("ABCDE", 1) == "B"
        assert mod.foo("ABCDE", -1) == "E"
        with SPyError.raises("W_IndexError", match="string index out of bound"):
            mod.foo("ABCDE", 5)
        with SPyError.raises("W_IndexError", match="string index out of bound"):
            mod.foo("ABCDE", -6)

    def test_compare(self):
        mod = self.compile("""
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

    @skip_backends("C", reason="`type` type not supported")
    def test_object_str_red(self):
        src = """
        def str_red_type() -> str:
            var t: type = i32   # note, this is a red variable
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
        assert mod.str_i32(-10) == "-10"
        assert mod.str_i32(123) == "123"
        assert mod.str_i8(-10) == "-10"
        assert mod.str_i8(127) == "127"
        assert mod.str_i8(-128) == "-128"
        assert mod.str_u8(0) == "0"
        assert mod.str_u8(255) == "255"
        assert mod.str_f64(-10.5) == "-10.5"
        assert mod.str_f64(0.0) in ("0", "0.0")
        assert mod.str_f64(3.14) == "3.14"
        assert mod.str_f64(123.456) == "123.456"
        assert mod.str_bool(True) == "True"
        assert mod.str_bool(False) == "False"

    def test_repr_blue(self):
        src = """
        def repr_blue() -> str:
            return repr(i32)
        """
        mod = self.compile(src)
        assert mod.repr_blue() == "<spy type 'i32'>"

    def test_repr_str(self):
        src = """
        def repr_str(s: str) -> str:
            return repr(s)

        def repr_str_foo() -> str:
            return repr("foo")
        """
        mod = self.compile(src)
        assert mod.repr_str_foo() == "'foo'"

        test_cases = [
            "foo",
            "",
            "hello\nworld",
            "tab\there",
            "cr\rhere",
            "back\\slash",
            "it's",
            "\x00",
            "\x1f",
            "café",
            "line1\nline2\ttabbed",
        ]
        for s in test_cases:
            assert mod.repr_str(s) == repr(s)

    @skip_backends("C", reason="`type` type not supported")
    def test_repr_red(self):
        src = """
        def repr_red_type() -> str:
            var t: type = i32   # note, this is a red variable
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
        assert mod.foo() == "None"

    def test_str_not_implemented(self):
        src = """
        def foo() -> str:
            return str(NotImplemented)
        """
        mod = self.compile(src)
        assert mod.foo() == "NotImplemented"

    def test_escaped_c_literal(self):
        # See https://github.com/spylang/spy/issues/255
        src = r"""
        def foo() -> str:
             return "\nBall"
        """
        mod = self.compile(src)
        assert mod.foo() == "\nBall"

    def test_str_replace(self):
        mod = self.compile("""
        def foo(s: str, old: str, new: str) -> str:
            return s.replace(old, new)
        """)
        assert mod.foo("hello world", "world", "spy") == "hello spy"

        # the following test cases have been adapted from
        # cpython/Lib/test/string_tests.py::test_replace

        # Operations on the empty string
        assert mod.foo("", "", "") == ""
        assert mod.foo("", "", "A") == "A"
        assert mod.foo("", "A", "") == ""
        assert mod.foo("", "A", "A") == ""
        # assert mod.foo("", "", "", 100) == ""  # count not supported
        # assert mod.foo("", "", "A", 100) == "A"  # count not supported
        # assert mod.foo("", "", "", sys.maxsize) == ""  # count not supported

        # interleave (from=="", 'to' gets inserted everywhere)
        assert mod.foo("A", "", "") == "A"
        assert mod.foo("A", "", "*") == "*A*"
        assert mod.foo("A", "", "*1") == "*1A*1"
        assert mod.foo("A", "", "*-#") == "*-#A*-#"
        assert mod.foo("AA", "", "*-") == "*-A*-A*-"
        # assert mod.foo("AA", "", "*-", -1) == "*-A*-A*-"  # count not supported
        # assert mod.foo("AA", "", "*-", sys.maxsize) == "*-A*-A*-"  # count not supported
        # assert mod.foo("AA", "", "*-", 4) == "*-A*-A*-"  # count not supported
        # assert mod.foo("AA", "", "*-", 3) == "*-A*-A*-"  # count not supported
        # assert mod.foo("AA", "", "*-", 2) == "*-A*-A"  # count not supported
        # assert mod.foo("AA", "", "*-", 1) == "*-AA"  # count not supported
        # assert mod.foo("AA", "", "*-", 0) == "AA"  # count not supported

        # single character deletion (from=="A", to=="")
        assert mod.foo("A", "A", "") == ""
        assert mod.foo("AAA", "A", "") == ""
        # assert mod.foo("AAA", "A", "", -1) == ""  # count not supported
        # assert mod.foo("AAA", "A", "", sys.maxsize) == ""  # count not supported
        # assert mod.foo("AAA", "A", "", 4) == ""  # count not supported
        # assert mod.foo("AAA", "A", "", 3) == ""  # count not supported
        # assert mod.foo("AAA", "A", "", 2) == "A"  # count not supported
        # assert mod.foo("AAA", "A", "", 1) == "AA"  # count not supported
        # assert mod.foo("AAA", "A", "", 0) == "AAA"  # count not supported
        assert mod.foo("AAAAAAAAAA", "A", "") == ""
        assert mod.foo("ABACADA", "A", "") == "BCD"
        # assert mod.foo("ABACADA", "A", "", -1) == "BCD"  # count not supported
        # assert mod.foo("ABACADA", "A", "", sys.maxsize) == "BCD"  # count not supported
        # assert mod.foo("ABACADA", "A", "", 5) == "BCD"  # count not supported
        # assert mod.foo("ABACADA", "A", "", 4) == "BCD"  # count not supported
        # assert mod.foo("ABACADA", "A", "", 3) == "BCDA"  # count not supported
        # assert mod.foo("ABACADA", "A", "", 2) == "BCADA"  # count not supported
        # assert mod.foo("ABACADA", "A", "", 1) == "BACADA"  # count not supported
        # assert mod.foo("ABACADA", "A", "", 0) == "ABACADA"  # count not supported
        assert mod.foo("ABCAD", "A", "") == "BCD"
        assert mod.foo("ABCADAA", "A", "") == "BCD"
        assert mod.foo("BCD", "A", "") == "BCD"
        assert mod.foo("*************", "A", "") == "*************"
        # assert mod.foo("^" + "A" * 1000 + "^", "A", "", 999) == "^A^"  # count not supported

        # substring deletion (from=="the", to=="")
        assert mod.foo("the", "the", "") == ""
        assert mod.foo("theater", "the", "") == "ater"
        assert mod.foo("thethe", "the", "") == ""
        assert mod.foo("thethethethe", "the", "") == ""
        assert mod.foo("theatheatheathea", "the", "") == "aaaa"
        assert mod.foo("that", "the", "") == "that"
        assert mod.foo("thaet", "the", "") == "thaet"
        assert mod.foo("here and there", "the", "") == "here and re"
        # assert mod.foo("here and there and there", "the", "", sys.maxsize) == "here and re and re"  # count not supported
        # assert mod.foo("here and there and there", "the", "", -1) == "here and re and re"  # count not supported
        # assert mod.foo("here and there and there", "the", "", 3) == "here and re and re"  # count not supported
        # assert mod.foo("here and there and there", "the", "", 2) == "here and re and re"  # count not supported
        # assert mod.foo("here and there and there", "the", "", 1) == "here and re and there"  # count not supported
        # assert mod.foo("here and there and there", "the", "", 0) == "here and there and there"  # count not supported
        assert mod.foo("here and there and there", "the", "") == "here and re and re"
        assert mod.foo("abc", "the", "") == "abc"
        assert mod.foo("abcdefg", "the", "") == "abcdefg"

        # substring deletion (from=="bob", to=="")
        assert mod.foo("bbobob", "bob", "") == "bob"
        assert mod.foo("bbobobXbbobob", "bob", "") == "bobXbob"
        assert mod.foo("aaaaaaabob", "bob", "") == "aaaaaaa"
        assert mod.foo("aaaaaaa", "bob", "") == "aaaaaaa"

        # single character replace in place (len(from)==len(to)==1)
        assert mod.foo("Who goes there?", "o", "o") == "Who goes there?"
        assert mod.foo("Who goes there?", "o", "O") == "WhO gOes there?"
        # assert mod.foo("Who goes there?", "o", "O", sys.maxsize) == "WhO gOes there?"  # count not supported
        # assert mod.foo("Who goes there?", "o", "O", -1) == "WhO gOes there?"  # count not supported
        # assert mod.foo("Who goes there?", "o", "O", 3) == "WhO gOes there?"  # count not supported
        # assert mod.foo("Who goes there?", "o", "O", 2) == "WhO gOes there?"  # count not supported
        # assert mod.foo("Who goes there?", "o", "O", 1) == "WhO goes there?"  # count not supported
        # assert mod.foo("Who goes there?", "o", "O", 0) == "Who goes there?"  # count not supported
        assert mod.foo("Who goes there?", "a", "q") == "Who goes there?"
        assert mod.foo("Who goes there?", "W", "w") == "who goes there?"
        assert mod.foo("WWho goes there?WW", "W", "w") == "wwho goes there?ww"
        assert mod.foo("Who goes there?", "?", "!") == "Who goes there!"
        assert mod.foo("Who goes there??", "?", "!") == "Who goes there!!"
        assert mod.foo("Who goes there?", ".", "!") == "Who goes there?"

        # substring replace in place (len(from)==len(to) > 1)
        assert mod.foo("This is a tissue", "is", "**") == "Th** ** a t**sue"
        # assert mod.foo("This is a tissue", "is", "**", sys.maxsize) == "Th** ** a t**sue"  # count not supported
        # assert mod.foo("This is a tissue", "is", "**", -1) == "Th** ** a t**sue"  # count not supported
        # assert mod.foo("This is a tissue", "is", "**", 4) == "Th** ** a t**sue"  # count not supported
        # assert mod.foo("This is a tissue", "is", "**", 3) == "Th** ** a t**sue"  # count not supported
        # assert mod.foo("This is a tissue", "is", "**", 2) == "Th** ** a tissue"  # count not supported
        # assert mod.foo("This is a tissue", "is", "**", 1) == "Th** is a tissue"  # count not supported
        # assert mod.foo("This is a tissue", "is", "**", 0) == "This is a tissue"  # count not supported
        assert mod.foo("bobob", "bob", "cob") == "cobob"
        assert mod.foo("bobobXbobobob", "bob", "cob") == "cobobXcobocob"
        assert mod.foo("bobob", "bot", "bot") == "bobob"

        # replace single character (len(from)==1, len(to)>1)
        assert mod.foo("Reykjavik", "k", "KK") == "ReyKKjaviKK"
        # assert mod.foo("Reykjavik", "k", "KK", -1) == "ReyKKjaviKK"  # count not supported
        # assert mod.foo("Reykjavik", "k", "KK", sys.maxsize) == "ReyKKjaviKK"  # count not supported
        # assert mod.foo("Reykjavik", "k", "KK", 2) == "ReyKKjaviKK"  # count not supported
        # assert mod.foo("Reykjavik", "k", "KK", 1) == "ReyKKjavik"  # count not supported
        # assert mod.foo("Reykjavik", "k", "KK", 0) == "Reykjavik"  # count not supported
        assert mod.foo("A.B.C.", ".", "----") == "A----B----C----"
        assert (
            mod.foo("...\u043c......<", "<", "&lt;") == "...\u043c......&lt;"
        )  # issue #15534
        assert mod.foo("Reykjavik", "q", "KK") == "Reykjavik"

        # replace substring (len(from)>1, len(to)!=len(from))
        assert (
            mod.foo("spam, spam, eggs and spam", "spam", "ham")
            == "ham, ham, eggs and ham"
        )
        # assert mod.foo("spam, spam, eggs and spam", "spam", "ham", sys.maxsize) == "ham, ham, eggs and ham"  # count not supported
        # assert mod.foo("spam, spam, eggs and spam", "spam", "ham", -1) == "ham, ham, eggs and ham"  # count not supported
        # assert mod.foo("spam, spam, eggs and spam", "spam", "ham", 4) == "ham, ham, eggs and ham"  # count not supported
        # assert mod.foo("spam, spam, eggs and spam", "spam", "ham", 3) == "ham, ham, eggs and ham"  # count not supported
        # assert mod.foo("spam, spam, eggs and spam", "spam", "ham", 2) == "ham, ham, eggs and spam"  # count not supported
        # assert mod.foo("spam, spam, eggs and spam", "spam", "ham", 1) == "ham, spam, eggs and spam"  # count not supported
        # assert mod.foo("spam, spam, eggs and spam", "spam", "ham", 0) == "spam, spam, eggs and spam"  # count not supported
        assert mod.foo("bobobob", "bobob", "bob") == "bobob"
        assert mod.foo("bobobobXbobobob", "bobob", "bob") == "bobobXbobob"
        assert mod.foo("BOBOBOB", "bob", "bobby") == "BOBOBOB"

        # assert mod.foo("one!two!three!", "!", "@", 1) == "one@two!three!"  # count not supported
        assert mod.foo("one!two!three!", "!", "") == "onetwothree"
        # assert mod.foo("one!two!three!", "!", "@", 2) == "one@two@three!"  # count not supported
        # assert mod.foo("one!two!three!", "!", "@", 3) == "one@two@three@"  # count not supported
        # assert mod.foo("one!two!three!", "!", "@", 4) == "one@two@three@"  # count not supported
        # assert mod.foo("one!two!three!", "!", "@", 0) == "one!two!three!"  # count not supported
        assert mod.foo("one!two!three!", "!", "@") == "one@two@three@"
        assert mod.foo("one!two!three!", "x", "@") == "one!two!three!"
        # assert mod.foo("one!two!three!", "x", "@", 2) == "one!two!three!"  # count not supported
        assert mod.foo("abc", "", "-") == "-a-b-c-"
        # assert mod.foo("abc", "", "-", 3) == "-a-b-c"  # count not supported
        # assert mod.foo("abc", "", "-", 0) == "abc"  # count not supported
        # assert mod.foo("abc", "ab", "--", 0) == "abc"  # count not supported
        assert mod.foo("abc", "xy", "--") == "abc"
