"""
This is a hack.

The goal is be able to parse lines such as:
    var x: i32 = 0
    const y: i32 = 0

We want to reuse the Python parser, but the lines above is not valid syntax.

The idea is to convert the code above into:
    var·x: i32 = 0
    const·y: i32 = 0

'·' is U+00B7 MIDDLE DOT, which is a valid unicode char for an indentifier. This means
that 'var·x' will be parsed as a single valide NAME token by Python, and then the SPy
parser will be able to special case it later.

The idea is the following:

1. tokenize the source

2. search for pairs of NAMEs starting with 'var' (from the point of view of
   the tokenizer, 'var' is a plain NAME)

3. replace 'var name' with 'var·name'

4. turn back the (modified) tokens into source code

5. parse the generated source code into an AST

It is important to make sure that whitespace is preserved as much as possible,
because we want the AST to contain location info which match the actual file
on disk. For this, we use the `untokenize` module (available on PyPI) which
does exactly that.
"""

import ast as py_ast
from io import BytesIO
from tokenize import DEDENT, NAME, TokenError, TokenInfo, tokenize

from spy.errors import SPyError
from spy.location import Loc
from spy.vendored import untokenize


def magic_py_parse(src: str, filename: str = "<string>") -> py_ast.Module:
    """
    Like ast.parse, but supports the new "var" and "const" syntax. See the module
    docstring for more info.
    """
    src2 = preprocess(src, filename)
    try:
        return py_ast.parse(src2, filename=filename)
    except SyntaxError as e:
        lineno = e.lineno or 1
        loc = Loc(filename, lineno, lineno, 0, -1)
        # this happens e.g. if we have an incomplete `if`, see test_magic_py_parse_error
        raise SPyError.simple("W_ParseError", e.msg, "", loc)


def get_tokens(src: str) -> list[TokenInfo]:
    readline = BytesIO(src.encode("utf-8")).readline
    return list(tokenize(readline))


def _update_scope_stack(
    tokens: list[TokenInfo], i: int, scope_stack: list[str]
) -> bool:
    tok = tokens[i]
    if tok.type == NAME and (
        (tok.string == "def" and i + 1 < len(tokens) and tokens[i + 1].type == NAME)
        or tok.string in ("while", "for", "if", "else")
    ):
        scope_stack.append(f"{tok.string}-{tokens[i + 1].string}")
        return True

    if tok.type == DEDENT and len(scope_stack) > 1:
        scope_stack.pop()

    return False


def _make_identifier(scope_stack: list[str], name: str, occurrence: int) -> str:
    return f"{'_'.join(scope_stack)}__{name}__occurance-{occurrence}"


def construct_SPy_specific_grammar(src: str) -> dict[str, TokenInfo]:
    tokens = get_tokens(src)
    n_tokens = len(tokens)
    i = 0

    scope_stack = ["module"]
    spy_grammar_tracker: dict[str, TokenInfo] = {}
    occurrences: dict[str, int] = {}
    while i < n_tokens:
        if _update_scope_stack(tokens, i, scope_stack):
            i += 1
            continue

        if (
            i > 0
            and tokens[i].type == NAME
            and tokens[i - 1].string in ("const", "var")
        ):
            prefix = f"{'_'.join(scope_stack)}__{tokens[i].string}"
            occurrence = occurrences.get(prefix, 1)
            occurrences[prefix] = occurrence + 1

            identifier = _make_identifier(scope_stack, tokens[i].string, occurrence)
            if identifier not in spy_grammar_tracker:
                string = tokens[i - 1].string
                spy_grammar_tracker[identifier] = tokens[i - 1]._replace(
                    string=string + " "
                )

        i += 1

    return spy_grammar_tracker


def reinsert_spy_specific_grammar(
    src: str, spy_grammar_tracker: dict[str, TokenInfo]
) -> list[TokenInfo]:
    tokens = get_tokens(src)
    n_tokens = len(tokens)
    i = 0

    scope_stack = ["module"]
    occurrences: dict[str, int] = {}
    while i < n_tokens:
        if _update_scope_stack(tokens, i, scope_stack):
            i += 1
            continue

        if tokens[i].type == NAME:
            prefix = f"{'_'.join(scope_stack)}__{tokens[i].string}"
            occurrence = occurrences.get(prefix, 1)
            occurrences[prefix] = occurrence + 1

            identifier = _make_identifier(scope_stack, tokens[i].string, occurrence)
            if identifier in spy_grammar_tracker:
                tokens.insert(i, spy_grammar_tracker[identifier])

        i += 1

    return tokens

def preprocess(src: str, filename: str = "<string>") -> str:
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

    while i < N - 1:
        tok0 = tokens[i]
        tok1 = tokens[i + 1]
        if tok0.type == NAME and tok0.string in ("var", "const") and tok1.type == NAME:
            # merge `var x` (or `const x`) into a single NAME token `var·x`
            # (resp. `const·x`), preserving the original column offsets by
            # padding the gap with U+00B7 MIDDLE DOT chars.
            var_l0, var_c0 = tok0.start
            var_l1, var_c1 = tok0.end
            name_l0, name_c0 = tok1.start
            name_l1, name_c1 = tok1.end
            assert var_l0 == var_l1 == name_l0 == name_l1, "multiline var not supported"
            dots = "·" * (name_c0 - var_c1)  # U+00B7 MIDDLE DOT
            newstring = tok0.string + dots + tok1.string
            newtok = TokenInfo(NAME, newstring, tok0.start, tok1.end, tok1.line)
            newtokens.append(newtok)
            i += 1
        else:
            newtokens.append(tok0)
        i += 1
    return untokenize.untokenize(newtokens)
