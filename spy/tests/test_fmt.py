import textwrap

from spy.magic_py_parse import reintroduce_spy_grammar


class TestFmt:
    def test_reintroduce_spy_grammar_var_and_const(self):
        src = textwrap.dedent(
            """
            def main():
                var·x: i32 = 1
                const····y: i32 = 2
            """
        )

        got = reintroduce_spy_grammar(src)
        expected = textwrap.dedent(
            """
            def main():
                var x: i32 = 1
                const y: i32 = 2
            """
        )
        assert got == expected

    def test_reintroduce_spy_grammar_non_spy_names_unchanged(self):
        src = "value = var_name + const_value\n"
        got = reintroduce_spy_grammar(src)
        assert got == src
