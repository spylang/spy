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


class TestColorFormatter:

    def test_ColorFormatter(self):
        fmt = ColorFormatter(use_colors=False)
        assert fmt.set('red', 'hello') == 'hello'
        #
        fmt = ColorFormatter(use_colors=True)
        assert fmt.set('red', 'hello') == '\x1b[31;01mhello\x1b[00m'
        assert fmt.set(None, 'hello') == 'hello'
