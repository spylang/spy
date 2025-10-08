import textwrap

from spy.ast_dump import dump
from spy.magic_py_parse import magic_py_parse, preprocess
from spy.parser import Parser
from spy.tests.support import expect_errors


def test_preprocess_plain():
    src1 = textwrap.dedent("""
    x: i32 = 100
    """)
    src2, var_locs = preprocess(src1)
    assert src1 == src2


def test_preprocess_var():
    src1 = textwrap.dedent("""
    var x: i32 = 100
    var    y     : i32 = 200
    """)
    src2, var_locs = preprocess(src1)
    expected = textwrap.dedent("""
    x    : i32 = 100
    y            : i32 = 200
    """)
    assert src2 == expected
    assert len(var_locs) == 2


def test_magic_py_parse():
    src = textwrap.dedent("""
    var x: i32 = 100
    y: i32 = 200
    """)
    py_mod = magic_py_parse(src)
    dumped = dump(py_mod, use_colors=False)
    expected = textwrap.dedent("""
    py:Module(
        body=[
            py:AnnAssign(
                target=py:Name(id='x', ctx=py:Store(), is_var=True),
                annotation=py:Name(id='i32', ctx=py:Load(), is_var=False),
                value=py:Constant(value=100, kind=None),
                simple=1,
            ),
            py:AnnAssign(
                target=py:Name(id='y', ctx=py:Store(), is_var=False),
                annotation=py:Name(id='i32', ctx=py:Load(), is_var=False),
                value=py:Constant(value=200, kind=None),
                simple=1,
            ),
        ],
        type_ignores=[],
    )
    """)
    assert dumped.strip() == expected.strip()


def test_magic_py_parse_error(tmpdir):
    src = textwrap.dedent("""
    def main() -> void:
        if 1:
    """)
    f = tmpdir.join("test.spy")
    f.write(src)
    parser = Parser(src, str(f))
    errors = expect_errors(
        "expected an indented block after 'if' statement on line 3", ("", "    if 1:")
    )
    with errors:
        parser.parse()


def test_magic_py_parse_tabs(tmpdir):
    src = textwrap.dedent("""
    def main() -> void:
        print('hello')
    \tprint('world')
    """)
    f = tmpdir.join("test.spy")
    f.write(src)
    parser = Parser(src, str(f))
    errors = expect_errors(
        "inconsistent use of tabs and spaces in indentation (<string>, line 4)",
        ("", "\tprint('world')"),
    )
    with errors:
        parser.parse()


def test_magic_py_parse_token_error(tmpdir):
    src = textwrap.dedent("""
    def main() -> void:
        '''
    """)
    f = tmpdir.join("test.spy")
    f.write(src)
    parser = Parser(src, str(f))
    errors = expect_errors("('EOF in multi-line string', (3, 5))", ("", "    '''"))
    with errors:
        parser.parse()
