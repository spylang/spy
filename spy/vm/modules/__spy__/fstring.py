"""
Implementation of f-strings.

The astcompiler desugars f-strings into calls to the metafuncs defined here and in
stdlib/_fstring.spy (which is implicitly imported, see ScopeAnalyzer.collect_JoinedStr):

    f"A{x!r}B"   ==>   fstring("A", f(x, "r", ""), "B")

  - _fstring::f wraps each interpolated part into a transient `FormattedVal` struct.
    The conversion is attached to its *static type*, so that it can be transported
    across metafunctions; the format spec is a normal runtime str field.

  - _fstring::fmt converts one part to `str`, dispatching on its static type.

  - __spy__::fstring synthesizes a force-inline ASTFunc which converts each part with
    fmt and assembles the result with an UnsafeFixedStrBuilder, similarly to what
    w_print does for print().

See also:
  - stdlib/_fstring.spy
  - w_print() in vm/modules/builtins.py
  - stdlib/_print.spy
"""

from typing import TYPE_CHECKING

from spy import ast
from spy.analyze.scope import ScopeAnalyzer
from spy.astcompile import astcompile
from spy.fqn import FQN
from spy.location import Loc
from spy.vm.b import B
from spy.vm.function import FuncParam, W_ASTFunc, W_FuncType
from spy.vm.object import W_Type
from spy.vm.opspec import W_MetaArg, W_OpSpec

from . import SPY

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@SPY.builtin_func(color="blue", kind="metafunc")
def w_fstring(vm: "SPyVM", *args_wam: W_MetaArg) -> W_OpSpec:
    """
    Interp-level implementation of f-strings.

    Ideally, we would like to implement it at applevel, but we cannot until we have
    `unroll()`.

    The astcompiler desugars f"..." into a call to this function, passing all
    the parts as arguments: f"A{x}B" ==> fstring("A", f(x, "", ""), "B").

    Similarly to w_print, we synthesize a force-inline ASTFunc, which assembles the
    final string using StrBuilder:

      - if wam_arg is a plain str, we append it as is
      - if it's a FormattedVal, we call fmt() on it

    @force_inline
    def impl(arg0: str, arg1: T1, ...) -> str:
        s1 = fmt(arg1)
        ...
        sb = UnsafeFixedStrBuilder(len(arg0) + len(s1) + ...)
        sb.append(arg0)
        sb.append(s1)
        ...
        return sb.build()
    """
    vm.import_("_fstring")
    vm.import_("strbuilder")

    func_args: list[ast.FuncArg] = []
    params: list[FuncParam] = []
    body: list[ast.Stmt] = []
    # name of the variable which holds the str for each part
    str_names: list[str] = []

    for i, wam in enumerate(args_wam):
        loc = wam.loc
        w_T = wam.w_static_T
        arg_name = f"arg{i}"
        func_args.append(
            ast.FuncArg(loc, arg_name, ast.FQNConst(loc, w_T.fqn), "simple")
        )
        params.append(FuncParam(w_T, "simple"))

        if w_T is B.w_str:
            # plain str: nothing to format
            str_names.append(arg_name)
            continue

        # s{i} = fmt(arg{i})
        s_name = f"s{i}"
        str_names.append(s_name)
        body.append(
            ast.Assign(
                loc=loc,
                target=ast.SingleTarget(loc, ast.StrLiteral(loc, s_name)),
                value=ast.Call(
                    loc=loc,
                    func=ast.FQNConst(loc, FQN("_fstring::fmt")),
                    args=[ast.Name(loc, arg_name)],
                ),
            )
        )

    # capacity = len(s0) + len(s1) + ...
    loc = Loc.here()
    lens = [
        ast.Call(
            loc=loc,
            func=ast.FQNConst(loc, B.w_len.fqn),
            args=[ast.Name(loc, name)],
        )
        for name in str_names
    ]
    capacity: ast.Expr
    if not lens:
        capacity = ast.Literal(loc, 0)
    else:
        capacity = lens[0]
        for l in lens[1:]:
            capacity = ast.BinOp(loc, "+", capacity, l)

    # sb = UnsafeFixedStrBuilder(capacity)
    w_StrBuilder = vm.lookup_global(FQN("strbuilder::UnsafeFixedStrBuilder"))
    assert isinstance(w_StrBuilder, W_Type)
    body.append(
        ast.Assign(
            loc=loc,
            target=ast.SingleTarget(loc, ast.StrLiteral(loc, "sb")),
            value=ast.Call(
                loc=loc,
                func=ast.FQNConst(loc, w_StrBuilder.fqn),
                args=[capacity],
            ),
        )
    )

    # sb.append(s{i})
    for name in str_names:
        body.append(
            ast.StmtExpr(
                loc=loc,
                value=ast.CallMethod(
                    loc=loc,
                    target=ast.Name(loc, "sb"),
                    method=ast.StrLiteral(loc, "append"),
                    args=[ast.Name(loc, name)],
                ),
            )
        )

    # return sb.build()
    body.append(
        ast.Return(
            loc=loc,
            value=ast.CallMethod(
                loc=loc,
                target=ast.Name(loc, "sb"),
                method=ast.StrLiteral(loc, "build"),
                args=[],
            ),
        )
    )

    fqn = FQN("__spy__::fstring::impl")
    fqn = vm.get_unique_FQN(fqn)
    funcdef = ast.FuncDef(
        loc=loc,
        stage="astcompiled",
        color="red",
        kind="plain",
        name="fstring",
        args=func_args,
        return_type=ast.FQNConst(loc, B.w_str.fqn),
        defaults=[],
        docstring=None,
        scoping_rules="pythonic",
        body=ast.Block(loc=loc, body=body),
        decorators=[],
    )
    module = ast.Module(
        loc=loc,
        stage="parsed",
        filename="<generated>",
        docstring=None,
        scoping_rules="pythonic",
        decls=[ast.GlobalFuncDef(loc, funcdef)],
    )
    sa = ScopeAnalyzer("__spy__", module)
    sa.analyze()
    module = astcompile(module, sa)
    funcdef = module.get_funcdef("fstring")
    w_functype = W_FuncType.new(params, w_restype=B.w_str)
    w_func = W_ASTFunc(
        w_functype,
        fqn,
        funcdef,
        closure=(),
        defaults_w=[],
        stage="astcompiled",
        is_force_inline=True,
    )
    vm.add_global(fqn, w_func)
    return W_OpSpec(w_func, list(args_wam))
