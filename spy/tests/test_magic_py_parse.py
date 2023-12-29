import textwrap
from spy.magic_py_parse import magic_py_parse, preprocess
from spy.ast_dump import dump

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
