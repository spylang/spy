import textwrap
from token import NAME
from tokenize import TokenInfo

from spy.analyze.fmt import format_python_source_with_ruff
from spy.magic_py_parse import (
    construct_SPy_specific_grammar,
    get_tokens,
    preprocess,
    reinsert_spy_specific_grammar,
)


class TestFmt:
    @staticmethod
    def _reinsert_tokens(mod: str) -> tuple[list[TokenInfo], list[TokenInfo]]:
        expected = get_tokens(mod)
        spy_grammar_tracker = construct_SPy_specific_grammar(mod)
        py_mod, _ = preprocess(mod)
        ruff_formatted = format_python_source_with_ruff(py_mod)
        got = reinsert_spy_specific_grammar(ruff_formatted, spy_grammar_tracker)
        return got, expected

    @staticmethod
    def _assert_name_tokens_match(
        got: list[TokenInfo], expected: list[TokenInfo]
    ) -> None:
        got_name_tokens = [
            token
            for token in got
            if token.type == NAME and token.string.strip() in ("const", "var")
        ]
        expected_name_tokens = [
            token
            for token in expected
            if token.type == NAME and token.string.strip() in ("const", "var")
        ]
        # breakpoint()
        assert len(got_name_tokens) == len(expected_name_tokens)
        for got_token, expected_token in zip(got_name_tokens, expected_name_tokens):
            # After ruff formatting. There are possibly new nodes
            # like `\n` or removed(INDENT) regarding ruff rules.
            # But nodes (NAME type) we focus now are `const`, `var`.
            assert got_token.type == expected_token.type
            assert got_token.string.strip() == expected_token.string.strip()
            assert got_token.line.strip().replace(
                " ", ""
            ) == expected_token.line.strip().replace(" ", "")

    def test_construct_SPy_specific_grammar_happy_path_1(self):
        mod = textwrap.dedent(
            """
            def foo():
                var x = 1
                const x = 2
            """
        )

        got = construct_SPy_specific_grammar(mod)
        expected = {
            "module_def-foo__x__occurrence-1": TokenInfo(
                type=1, string="var ", start=(3, 4), end=(3, 7), line="    var x = 1\n"
            ),
            "module_def-foo__x__occurrence-2": TokenInfo(
                type=1,
                string="const ",
                start=(4, 4),
                end=(4, 9),
                line="    const x = 2\n",
            ),
        }
        assert got == expected

    def test_construct_SPy_specific_grammar_happy_path_2_nested(self):
        mod = textwrap.dedent(
            """
            def foo():
                var x = 1
                const x = 2
                def alevel():
                    y = 10
                    const allow_u = "ALLOW"
            """
        )

        got = construct_SPy_specific_grammar(mod)
        expected = {
            "module_def-foo__x__occurrence-1": TokenInfo(
                type=1, string="var ", start=(3, 4), end=(3, 7), line="    var x = 1\n"
            ),
            "module_def-foo__x__occurrence-2": TokenInfo(
                type=1,
                string="const ",
                start=(4, 4),
                end=(4, 9),
                line="    const x = 2\n",
            ),
            "module_def-foo_def-alevel__allow_u__occurrence-1": TokenInfo(
                type=1,
                string="const ",
                start=(7, 8),
                end=(7, 13),
                line='        const allow_u = "ALLOW"\n',
            ),
        }

        assert got == expected

    def test_construct_SPy_specific_grammar_no_spy_specific_grammar(self):
        mod = textwrap.dedent(
            """
            def foo():
                x = 1
                y = 2
            """
        )

        got = construct_SPy_specific_grammar(mod)

        assert got == {}

    def test_construct_SPy_specific_grammar_primitive_type_names(self):
        mod = textwrap.dedent(
            """
            def foo():
                var listA: list[int]  = [5, 2, 6, 8]
                const dictA: dict[int, int] = {0: 555, 10: 888}
                var tupleA: tuple[str] = ("hello", "world")
            """
        )

        got = construct_SPy_specific_grammar(mod)
        expected = {
            "module_def-foo__listA__occurrence-1": TokenInfo(
                type=1,
                string="var ",
                start=(3, 4),
                end=(3, 7),
                line="    var listA: list[int]  = [5, 2, 6, 8]\n",
            ),
            "module_def-foo__dictA__occurrence-1": TokenInfo(
                type=1,
                string="const ",
                start=(4, 4),
                end=(4, 9),
                line="    const dictA: dict[int, int] = {0: 555, 10: 888}\n",
            ),
            "module_def-foo__tupleA__occurrence-1": TokenInfo(
                type=1,
                string="var ",
                start=(5, 4),
                end=(5, 7),
                line='    var tupleA: tuple[str] = ("hello", "world")\n',
            ),
        }

        assert got == expected

    def test_reinsert_spy_specific_grammar_happy_path_1(self):
        mod = textwrap.dedent(
            """const x = 10
            """
        )
        got, expected = self._reinsert_tokens(mod)
        self._assert_name_tokens_match(got, expected)

    def test_reinsert_spy_specific_grammar_happy_path_2_nested(self):
        mod = textwrap.dedent(
            """def main():
                var x = 1
            """
        )
        got, expected = self._reinsert_tokens(mod)
        self._assert_name_tokens_match(got, expected)

    def test_reinsert_spy_specific_grammar_no_spy_specific_grammar(self):
        mod = textwrap.dedent(
            """def main():
                x = 1
                y = 2
            """
        )
        got, expected = self._reinsert_tokens(mod)
        self._assert_name_tokens_match(got, expected)

    def test_reinsert_spy_specific_grammar_primitive_type_names(self):
        mod = textwrap.dedent(
            """def main():
                var listA: list[int]  = [5, 2, 6, 8]
                const dictA: dict[int, int] = {0: 555, 10: 888}
                var tupleA: tuple[str] = ("hello", "world")
            """
        )
        got, expected = self._reinsert_tokens(mod)
        self._assert_name_tokens_match(got, expected)
