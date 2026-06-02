import ast as py_ast
import textwrap

from spy.magic_py_parse import magic_py_parse, preprocess
from spy.parser import Parser
from spy.tests.support import expect_errors


def test_preprocess_plain():
    src1 = textwrap.dedent("""
    x: i32 = 100
    """)
    src2 = preprocess(src1)
    assert src1 == src2


def test_preprocess_var():
    src1 = textwrap.dedent("""
    var x: i32 = 100
    var    y     : i32 = 200
    """)
    src2 = preprocess(src1)
    expected = textwrap.dedent("""
    var·x: i32 = 100
    var····y     : i32 = 200
    """)
    assert src2 == expected


def test_preprocess_const():
    src1 = textwrap.dedent("""
    const x: i32 = 100
    const    y     : i32 = 200
    """)
    src2 = preprocess(src1)
    expected = textwrap.dedent("""
    const·x: i32 = 100
    const····y     : i32 = 200
    """)
    assert src2 == expected


def test_magic_py_parse():
    src = textwrap.dedent("""
    var x: i32 = 100
    const y: i32 = 200
    z: i32 = 300

    """)
    py_mod = magic_py_parse(src)
    targets = [
        stmt.target.id
        for stmt in py_mod.body
        if isinstance(stmt, py_ast.AnnAssign) and isinstance(stmt.target, py_ast.Name)
    ]
    assert targets == ["var·x", "const·y", "z"]


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
