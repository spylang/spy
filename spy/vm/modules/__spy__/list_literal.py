"""
Implementation of list literals.

The astcompiler desugars list literals into calls to __spy__::list_literal:

    []         ==>   __spy__::list_literal()
    [a, b, c]  ==>   __spy__::list_literal(a, b, c)

See also ASTCompiler.compile_expr_List.
"""

from typing import TYPE_CHECKING

from spy import ast
from spy.analyze.scope import ScopeAnalyzer
from spy.astcompile import astcompile
from spy.fqn import FQN
from spy.location import Loc
from spy.vm.function import FuncParam, W_ASTFunc, W_FuncType
from spy.vm.object import W_Type
from spy.vm.opspec import W_MetaArg, W_OpSpec

from . import SPY

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@SPY.builtin_func(color="blue", kind="metafunc")
def w_list_literal(vm: "SPyVM", *args_wam: W_MetaArg) -> W_OpSpec:
    """
    Interp-level implementation of list literals.

    Ideally, we would like to implement it at applevel, but we cannot until we have
    `unroll()`.

    The astcompiler desugars `[...]` into a call to this function, which generates the
    actual code to create a list by calling `list[T]::new` and `list[T]::_push`.

    The empty list `[]` is special: it is the `__spy__::empty_list` singleton, which is
    converted to the right list type by `__convert_from__`.
    """
    if len(args_wam) == 0:
        return W_OpSpec.const(SPY.w_empty_list)
    loc = Loc.here()
    w_itemtype = args_wam[0].w_static_T
    for wam in args_wam[1:]:
        w_itemtype = vm.union_type(w_itemtype, wam.w_static_T)

    w_ListType = vm.lookup_global(FQN("_list::list"))
    w_T = vm.getitem_w(w_ListType, w_itemtype, loc=args_wam[0].loc)  # list[i32]
    assert isinstance(w_T, W_Type)
    w_push = vm.lookup_global(w_T.fqn.join("_push"))
    fqn_T = vm.make_fqn_const(w_T)
    fqn_push = vm.make_fqn_const(w_push)

    result: ast.Expr = ast.Call(loc, ast.FQNConst(loc, fqn_T), [])
    for i, wam in enumerate(args_wam):
        result = ast.Call(
            loc=wam.loc,
            func=ast.FQNConst(wam.loc, fqn_push),
            args=[result, ast.Name(wam.loc, f"arg{i}")],
        )

    func_args: list[ast.FuncArg] = []
    params: list[FuncParam] = []
    for i, wam in enumerate(args_wam):
        w_argT = wam.w_static_T
        func_args.append(
            ast.FuncArg(
                wam.loc,
                f"arg{i}",
                ast.FQNConst(wam.loc, vm.make_fqn_const(w_argT)),
                "simple",
            )
        )
        params.append(FuncParam(w_argT, "simple"))

    fqn = vm.get_unique_FQN(FQN("__spy__::list_literal::impl"))
    funcdef = ast.FuncDef(
        loc=loc,
        stage="astcompiled",
        color="red",
        kind="plain",
        name="list_literal",
        args=func_args,
        return_type=ast.FQNConst(loc, fqn_T),
        defaults=[],
        docstring=None,
        scoping_rules="pythonic",
        body=ast.Block(loc=loc, body=[ast.Return(loc, result)]),
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
    funcdef = module.get_funcdef("list_literal")
    w_functype = W_FuncType.new(params, w_restype=w_T)
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
