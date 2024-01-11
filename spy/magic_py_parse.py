"""
This is a hack.

The goal is be able to parse lines such as:
    var x: i32 = 0

We want to reuse the Python parser, but the line above is not valid syntax.

The idea is the following:

1. tokenize the source

2. search for pairs of NAMEs starting with 'var' (from the point of view of
   the tokenizer, 'var' is a plain NAME

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

from dataclasses import dataclass
import ast as py_ast
from tokenize import tokenize, NUMBER, STRING, NAME, OP, TokenInfo
from io import BytesIO
import untokenize
import spy.ast_dump

@dataclass(frozen=True)
class LocInfo:
    lineno: int
    end_lineno: int
    col_offset: int
    end_col_offset: int

def magic_py_parse(src: str) -> py_ast.Module:
    """
    Like ast.parse, but supports the new "var" syntax. See the module
    docstring for more info.
    """
    src2, var_locs = preprocess(src)
    py_mod = py_ast.parse(src2)

    for node in py_ast.walk(py_mod):
        if isinstance(node, py_ast.Name):
            assert node.end_lineno is not None
            assert node.end_col_offset is not None
            loc = LocInfo(node.lineno, node.end_lineno,
                          node.col_offset, node.end_col_offset)
            node.is_var = loc in var_locs

    return py_mod

def get_tokens(src: str) -> list[TokenInfo]:
    readline = BytesIO(src.encode('utf-8')).readline
    return list(tokenize(readline))

def preprocess(src: str) -> tuple[str, set[LocInfo]]:
    tokens = get_tokens(src)
    newtokens = []
    i = 0
    N = len(tokens)
    var_locs = set()

    while i < N-1:
        tok0 = tokens[i]
        tok1 = tokens[i+1]
        if tok0.type == NAME and tok0.string == 'var' and tok1.type == NAME:
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
            assert var_l0 == var_l1 == name_l0 == name_l1, \
                'multiline var not supported'
            spaces = ' ' * (name_c0 - var_c0)
            newtok = TokenInfo(NAME, tok1.string + spaces,
                               tok0.start, tok1.end, tok1.line)
            newtokens.append(newtok)
            # compute the location info of the future ast.Name
            loc = LocInfo(
                lineno = var_l0,
                end_lineno = var_l0,
                col_offset = var_c0,
                end_col_offset = var_c0 + len(tok1.string)
            )
            var_locs.add(loc)
            i += 1
        else:
            newtokens.append(tok0)
        i += 1
    src2 = untokenize.untokenize(newtokens)
    return src2, var_locs
