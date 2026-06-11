import textwrap

from spy.magic_py_parse import undo_preprocess


class TestFmt:
    def test_undo_preprocess_var_and_const(self):
        src = textwrap.dedent(
            """
            def main():
                var·x: i32 = 1
                const····y: i32 = 2
            """
        )

        got = undo_preprocess(src)
        expected = textwrap.dedent(
            """
            def main():
                var x: i32 = 1
                const y: i32 = 2
            """
        )
        assert got == expected

    def test_undo_preprocess_non_spy_names_unchanged(self):
        src = "value = var_name + const_value\n"
        got = undo_preprocess(src)
        assert got == src
