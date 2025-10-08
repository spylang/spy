import pytest
import textwrap
from spy.textbuilder import TextBuilder, ColorFormatter

class TestTextBuilder:

    def test_simple(self):
        b = TextBuilder()
        assert b.build() == ""
        b.write("hello")
        assert b.build() == "hello"
        b.write(" world")
        assert b.build() == "hello world"
        b.writeline(" newline")
        b.writeline("foo")
        assert b.build() == textwrap.dedent("""\
        hello world newline
        foo
        """)

    def test_indent(self):
        b = TextBuilder()
        b.wl("begin")
        with b.indent():
            b.wl("AAA")
            b.wl("BBB")
            with b.indent():
                b.wl("BBB.1")
                b.wl("BBB.2")
            b.wl("CCC")
        b.wl("end")
        s = b.build()
        assert s == textwrap.dedent("""\
        begin
            AAA
            BBB
                BBB.1
                BBB.2
            CCC
        end
        """)

    def test_use_colors(self):
        b = TextBuilder(use_colors=True)
        b.wl("hello")
        b.wl("world", color="red")
        s = b.build()
        expected = textwrap.dedent("""\
        hello
        \x1b[31;01mworld\x1b[00m
        """)
        assert s == expected

    def test_nested(self):
        outer = TextBuilder()
        outer.wl("begin")
        inner = outer.make_nested_builder()
        outer.wl("end")
        inner.wl("AAA")
        inner.wl("BBB")
        s = outer.build()
        expected = textwrap.dedent("""\
        begin
        AAA
        BBB
        end
        """)
        assert s == expected

    def test_nested_empty(self):
        outer = TextBuilder()
        outer.wl("begin")
        inner = outer.make_nested_builder()
        outer.wl("end")
        s = outer.build()
        expected = textwrap.dedent("""\
        begin
        end
        """)
        assert s == expected

    def test_nested_indent(self):
        outer = TextBuilder()
        outer.wl("begin")
        with outer.indent():
            inner = outer.make_nested_builder()
        outer.wl("end")
        inner.wl("AAA")
        inner.wl("BBB")
        s = outer.build()
        expected = textwrap.dedent("""\
        begin
            AAA
            BBB
        end
        """)
        assert s == expected

    def test_nested_error(self):
        outer = TextBuilder()
        outer.w("begin")
        with pytest.raises(ValueError, match="attach_nested_builder can be "
                           "called only after a newline"):
            inner = outer.make_nested_builder()

    def test_nested_detached(self):
        outer = TextBuilder()
        outer.wl("AAA")
        inner = outer.make_nested_builder(detached=True)
        inner.wl("CCC")
        outer.wl("BBB")
        outer.attach_nested_builder(inner)
        s = outer.build()
        expected = textwrap.dedent("""\
        AAA
        BBB
        CCC
        """)
        assert s == expected

    @pytest.mark.xfail(reason="fixme") # see attach_nested_builder.__doc__
    def test_detached_indent(self):
        outer = TextBuilder()
        inner = outer.make_nested_builder(detached=True)
        inner.wl("AAA")
        inner.wl("BBB")
        outer.wl("begin")
        with outer.indent():
            outer.attach_nested_builder(inner)
        outer.wl("end")
        s = outer.build()
        expected = textwrap.dedent("""\
        begin
            AAA
            BBB
        end
        """)
        assert s == expected

    def test_writeblock(self):
        b = TextBuilder()
        b.wl("hello")
        b.wb("""
            one
            two
            three
        """)
        b.wl("world")
        s = b.build()
        expected = textwrap.dedent("""\
        hello
        one
        two
        three
        world
        """)
        assert s == expected

    def test_lineno(self):
        b = TextBuilder()
        assert b.lineno == 1
        b.wl("one")
        assert b.lineno == 2
        b.wb("""
        two
        three
        four
        """)
        assert b.lineno == 5

class TestColorFormatter:

    def test_ColorFormatter(self):
        fmt = ColorFormatter(use_colors=False)
        assert fmt.set("red", "hello") == "hello"
        #
        fmt = ColorFormatter(use_colors=True)
        assert fmt.set("red", "hello") == "\x1b[31;01mhello\x1b[00m"
        assert fmt.set(None, "hello") == "hello"

    def test_ColorFormatter_bg(self):
        fmt = ColorFormatter(use_colors=False)
        assert fmt.set("red", "hello", bg="blue") == "hello"
        #
        fmt = ColorFormatter(use_colors=True)
        assert fmt.set("red", "hello", bg="blue") == "\x1b[31;01;104mhello\x1b[00m"
        assert fmt.set(None, "hello", bg="blue") == "\x1b[104mhello\x1b[00m"
        assert fmt.set("red", "hello", bg=None) == "\x1b[31;01mhello\x1b[00m"

    def test_TextBuilder_bg(self):
        b = TextBuilder(use_colors=True)
        b.wl("hello")
        b.wl("world", color="red", bg="blue")
        s = b.build()
        expected = textwrap.dedent("""\
        hello
        \x1b[31;01;104mworld\x1b[00m
        """)
        assert s == expected

    def test_writeblock_bg(self):
        b = TextBuilder(use_colors=True)
        b.wl("hello")
        b.wb("""
            one
            two
        """, color="green", bg="darkred")
        s = b.build()
        expected = textwrap.dedent("""\
        hello
        \x1b[32;01;41mone\x1b[00m
        \x1b[32;01;41mtwo\x1b[00m
        """)
        assert s == expected

    def test_color_contextmanager(self):
        b = TextBuilder(use_colors=True)

        # Basic color context
        with b.color("red"):
            b.write("red text")
        b.writeline()

        # Nested color contexts with background
        with b.color("red"):
            b.write("red text ")
            with b.color(bg="green"):
                b.write("red on green ")
                b.wl("This is purple on green.", color="purple")
                with b.color("blue"):
                    b.write("blue on green")
        b.writeline()

        # Test inheritance of colors
        with b.color("yellow"):
            b.write("yellow text ")
            with b.color(bg="blue"):
                b.write("yellow on blue ")
                with b.color(None, bg="red"):
                    b.write("yellow on red")
        b.writeline()

        # Test overriding both colors
        with b.color("green", bg="black"):
            b.write("green on black ")
            with b.color("white", bg="blue"):
                b.write("white on blue")
        b.writeline()

        # Test that explicit colors override context
        with b.color("red"):
            b.write("red from context ")
            b.write("blue explicitly", color="blue")
        b.writeline()

        s = b.build()

        # Check that the text is present with appropriate ANSI codes
        assert "\x1b[31;01mred text\x1b[00m" in s
        assert "\x1b[31;01mred text \x1b[00m" in s
        assert "\x1b[31;01;102mred on green \x1b[00m" in s
        assert "\x1b[35;102mThis is purple on green.\x1b[00m" in s
        assert "\x1b[34;01;102mblue on green\x1b[00m" in s
        assert "\x1b[33;01myellow text \x1b[00m" in s
        assert "\x1b[33;01;104myellow on blue \x1b[00m" in s
        assert "\x1b[33;01;101myellow on red\x1b[00m" in s
        assert "\x1b[32;01;40mgreen on black \x1b[00m" in s
        assert "\x1b[37;01;104mwhite on blue\x1b[00m" in s
        assert "\x1b[31;01mred from context \x1b[00m" in s
        assert "\x1b[34;01mblue explicitly\x1b[00m" in s

    def test_color_contextmanager_no_colors(self):
        # Test that the contextmanager works even when colors are disabled
        b = TextBuilder(use_colors=False)

        with b.color("red"):
            b.write("red text ")
            with b.color(bg="green"):
                b.write("red on green ")
                with b.color("blue"):
                    b.write("blue on green")
        b.writeline()

        s = b.build().rstrip("\n")
        assert s == "red text red on green blue on green"

