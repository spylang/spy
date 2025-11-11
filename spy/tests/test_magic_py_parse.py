import textwrap
from pathlib import Path

from spy.ast_dump import dump
from spy.magic_py_parse import magic_py_parse, preprocess
from spy.parser import Parser
from spy.tests.support import expect_errors


def test_preprocess_plain():
    src1 = textwrap.dedent("""
    x: i32 = 100
    """)
    src2, varkind_locs = preprocess(src1)
    assert src1 == src2


def test_preprocess_var():
    src1 = textwrap.dedent("""
    var x: i32 = 100
    var    y     : i32 = 200
    """)
    src2, varkind_locs = preprocess(src1)
    expected = textwrap.dedent("""
    x    : i32 = 100
    y            : i32 = 200
    """)
    assert src2 == expected
    assert len(varkind_locs) == 2
    assert list(varkind_locs.values()) == ["var", "var"]


def test_preprocess_const():
    src1 = textwrap.dedent("""
    const x: i32 = 100
    const    y     : i32 = 200
    """)
    src2, varkind_locs = preprocess(src1)
    expected = textwrap.dedent("""
    x      : i32 = 100
    y              : i32 = 200
    """)
    assert src2 == expected
    assert len(varkind_locs) == 2
    assert list(varkind_locs.values()) == ["const", "const"]


def test_magic_py_parse():
    src = textwrap.dedent("""
    var x: i32 = 100
    const y: i32 = 200
    z: i32 = 300

    """)
    py_mod = magic_py_parse(src)
    dumped = dump(py_mod, use_colors=False)
    expected = textwrap.dedent("""
    py:Module(
        body=[
            py:AnnAssign(
                target=py:Name(id='x', ctx=py:Store(), spy_varkind='var'),
                annotation=py:Name(id='i32', ctx=py:Load(), spy_varkind=None),
                value=py:Constant(value=100, kind=None),
                simple=1,
            ),
            py:AnnAssign(
                target=py:Name(id='y', ctx=py:Store(), spy_varkind='const'),
                annotation=py:Name(id='i32', ctx=py:Load(), spy_varkind=None),
                value=py:Constant(value=200, kind=None),
                simple=1,
            ),
            py:AnnAssign(
                target=py:Name(id='z', ctx=py:Store(), spy_varkind=None),
                annotation=py:Name(id='i32', ctx=py:Load(), spy_varkind=None),
                value=py:Constant(value=300, kind=None),
                simple=1,
            ),
        ],
        type_ignores=[],
    )
    """)
    assert dumped.strip() == expected.strip()


def test_magic_py_parse_error(tmp_path: Path):
    src = textwrap.dedent("""
    def main() -> void:
        if 1:
    """)
    f = tmp_path / "test.spy"
    f.write_text(src)
    parser = Parser(src, str(f))
    errors = expect_errors(
        "expected an indented block after 'if' statement on line 3", ("", "    if 1:")
    )
    with errors:
        parser.parse()


def test_magic_py_parse_tabs(tmp_path: Path):
    src = textwrap.dedent("""
    def main() -> void:
        print('hello')
    \tprint('world')
    """)
    f = tmp_path / "test.spy"
    f.write_text(src)
    parser = Parser(src, str(f))
    errors = expect_errors(
        "inconsistent use of tabs and spaces in indentation (<string>, line 4)",
        ("", "\tprint('world')"),
    )
    with errors:
        parser.parse()


def test_magic_py_parse_token_error(tmp_path: Path):
    src = textwrap.dedent("""
    def main() -> void:
        '''
    """)
    f = tmp_path / "test.spy"
    f.write_text(src)
    parser = Parser(src, str(f))
    errors = expect_errors("('EOF in multi-line string', (3, 5))", ("", "    '''"))
    with errors:
        parser.parse()
