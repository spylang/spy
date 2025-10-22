"""
This is a hack.

The goal is be able to parse lines such as:
    var x: i32 = 0
    const y: i32 = 0

We want to reuse the Python parser, but the lines above is not valid syntax.

The idea is the following:

1. tokenize the source

2. search for pairs of NAMEs starting with 'var' (from the point of view of
   the tokenizer, 'var' is a plain NAME)

3. remove the 'var' token, and keep track of the location in which it was seen

4. turn back the (modified) tokens into source code

5. parse the generated source code into an AST

6. add a new field "is_var: bool" to all ast.Name nodes, using the infos
   gathered at point (3)

It is important to make sure that whitespace is preserved as much as possible,
because we want the AST to contain location info which match the actual file
on disk. For this, we use the `untokenize` module (available on PyPI) which
does exactly that.
"""

import ast as py_ast
from dataclasses import dataclass
from io import BytesIO
from tokenize import NAME, TokenError, TokenInfo, tokenize
from typing import Literal

from spy.errors import SPyError
from spy.location import Loc
from spy.vendored import untokenize

VarKind = Literal["var", "const"]


@dataclass(frozen=True)
class LocInfo:
    lineno: int
    end_lineno: int
    col_offset: int
    end_col_offset: int


def magic_py_parse(src: str, filename: str = "<string>") -> py_ast.Module:
    """
    Like ast.parse, but supports the new "var" and "const" syntax. See the module
    docstring for more info.
    """
    src2, varkind_locs = preprocess(src, filename)
    try:
        py_mod = py_ast.parse(src2, filename=filename)
    except SyntaxError as e:
        lineno = e.lineno or 1
        loc = Loc(filename, lineno, lineno, 0, -1)
        # this happens e.g. if we have an incomplete `if`, see test_magic_py_parse_error
        raise SPyError.simple("W_ParseError", e.msg, "", loc)

    for node in py_ast.walk(py_mod):
        if isinstance(node, py_ast.Name):
            assert node.end_lineno is not None
            assert node.end_col_offset is not None
            loc_info = LocInfo(
                node.lineno, node.end_lineno, node.col_offset, node.end_col_offset
            )
            node.spy_varkind = varkind_locs.get(loc_info)

    return py_mod


def get_tokens(src: str) -> list[TokenInfo]:
    readline = BytesIO(src.encode("utf-8")).readline
    return list(tokenize(readline))


def preprocess(
    src: str, filename: str = "<string>"
) -> tuple[str, dict[LocInfo, VarKind]]:
    try:
        tokens = get_tokens(src)
    except (SyntaxError, TokenError) as e:
        lineno = getattr(e, "lineno", None)
        if lineno is None and isinstance(e, TokenError):
            lineno = e.args[1][0] if e.args and isinstance(e.args[1], tuple) else 1
        if lineno is None:
            lineno = 1
        loc = Loc(filename, lineno, lineno, 0, -1)
        # this happens when e.g. we mix tabs and spaces, see test_magic_py_parse_tab
        raise SPyError.simple("W_ParseError", str(e), "", loc)
    newtokens = []
    i = 0
    N = len(tokens)
    varkind_locs: dict[LocInfo, VarKind] = {}

    while i < N - 1:
        tok0 = tokens[i]
        tok1 = tokens[i + 1]
        if tok0.type == NAME and tok0.string in ("var", "const") and tok1.type == NAME:
            varkind: VarKind = tok0.string  # type: ignore
            # tok0 is 'var'
            # tok1 is the name
            # basically, we want to turn:
            #     var x: i32 = 100
            # into:
            #     x    : i32 = 100
            #
            # so that the Locs in the final AST maps to the correct places in
            # the original source code.
            var_l0, var_c0 = tok0.start
            var_l1, var_c1 = tok0.end
            name_l0, name_c0 = tok1.start
            name_l1, name_c1 = tok1.end
            assert var_l0 == var_l1 == name_l0 == name_l1, "multiline var not supported"
            spaces = " " * (name_c0 - var_c0)
            newtok = TokenInfo(
                NAME, tok1.string + spaces, tok0.start, tok1.end, tok1.line
            )
            newtokens.append(newtok)
            # compute the location info of the future ast.Name
            loc_info = LocInfo(
                lineno=var_l0,
                end_lineno=var_l0,
                col_offset=var_c0,
                end_col_offset=var_c0 + len(tok1.string),
            )
            varkind_locs[loc_info] = varkind
            i += 1
        else:
            newtokens.append(tok0)
        i += 1
    src2 = untokenize.untokenize(newtokens)
    return src2, varkind_locs
