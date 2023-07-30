import pytest
import textwrap
from spy.textbuilder import TextBuilder, ColorFormatter

class TestTextBuilder:

    def test_simple(self):
        b = TextBuilder()
        assert b.build() == ''
        b.write('hello')
        assert b.build() == 'hello'
        b.write(' world')
        assert b.build() == 'hello world'
        b.writeline(' newline')
        b.writeline('foo')
        assert b.build() == textwrap.dedent("""\
        hello world newline
        foo
        """)

    def test_indent(self):
        b = TextBuilder()
        b.wl('begin')
        with b.indent():
            b.wl('AAA')
            b.wl('BBB')
            with b.indent():
                b.wl('BBB.1')
                b.wl('BBB.2')
            b.wl('CCC')
        b.wl('end')
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
        b.wl('hello')
        b.wl('world', color='red')
        s = b.build()
        expected = textwrap.dedent("""\
        hello
        \x1b[31;01mworld\x1b[00m
        """)
        assert s == expected

    def test_nested(self):
        outer = TextBuilder()
        outer.wl('begin')
        inner = outer.make_nested_builder()
        outer.wl('end')
        inner.wl('AAA')
        inner.wl('BBB')
        s = outer.build()
        expected = textwrap.dedent("""\
        begin
        AAA
        BBB
        end
        """)
        assert s == expected

    def test_nested_indent(self):
        outer = TextBuilder()
        outer.wl('begin')
        with outer.indent():
            inner = outer.make_nested_builder()
        outer.wl('end')
        inner.wl('AAA')
        inner.wl('BBB')
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
        outer.w('begin')
        with pytest.raises(ValueError, match='make_nested_builder can be '
                           'called only after a newline'):
            inner = outer.make_nested_builder()


class TestColorFormatter:

    def test_ColorFormatter(self):
        fmt = ColorFormatter(use_colors=False)
        assert fmt.set('red', 'hello') == 'hello'
        #
        fmt = ColorFormatter(use_colors=True)
        assert fmt.set('red', 'hello') == '\x1b[31;01mhello\x1b[00m'
        assert fmt.set(None, 'hello') == 'hello'
