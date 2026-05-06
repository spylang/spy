"""
Helpers for @force_inline.
"""

from spy import ast
from spy.errors import SPyError
from spy.vm.function import W_ASTFunc
from spy.vm.primitive import TYPES


def validate_force_inline(w_func: W_ASTFunc) -> None:
    body = w_func.funcdef.body
    last_stmt = body[-1] if body else None
    returns_none = w_func.w_functype.w_restype is TYPES.w_NoneType
    if not returns_none and not isinstance(last_stmt, ast.Return):
        err = SPyError(
            "W_TypeError",
            "@force_inline requires a single tail return",
        )
        err.add("error", "missing `return` at the end of the body", w_func.def_loc)
        raise err

    for ret in w_func.funcdef.walk(ast.Return):
        if ret is not last_stmt:
            # found a 'return' in the wrong place
            err = SPyError(
                "W_TypeError",
                "@force_inline requires a single tail return",
            )
            err.add(
                "error",
                "`return` must be the last statement of the body",
                ret.loc,
            )
            raise err
