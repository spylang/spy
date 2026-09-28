from typing import TYPE_CHECKING

from spy import ast
from spy.analyze.scope import ScopeAnalyzer
from spy.astcompile import astcompile
from spy.fqn import FQN
from spy.location import Loc
from spy.vm.b import B
from spy.vm.function import FuncParam, W_ASTFunc, W_Func, W_FuncType
from spy.vm.object import W_Type
from spy.vm.opspec import W_MetaArg, W_OpSpec

from . import SPY

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@SPY.builtin_func(color="blue", kind="metafunc")
def w_fstring(vm: "SPyVM", *args_wam: W_MetaArg) -> W_OpSpec:
    """
    Interp-level implementation of f-strings.

    The astcompiler desugars f"..." into a call to this function, passing all
    the parts as arguments: f"A{x}B" ==> fstring("A", x, "B").

    Similarly to w_print, we synthesize a force-inline ASTFunc, which converts
    each part by calling _fstring::format1[T] and then assembles the result
    with a StrBuilder:

        @force_inline
        def impl(arg0: T0, arg1: T1, ...) -> str:
            s0 = format1[T0, None, None](arg0)
            s1 = format1[T1, None, None](arg1)
            ...
            sb = StrBuilder(len(s0) + len(s1) + ...)
            sb.append(s0)
            sb.append(s1)
            ...
            return sb.build()

    Note: at the moment we don't have __format__, so conversions and format
    specs are rejected by the astcompiler, and format1 is always called with
    conversion=None and format_spec=None.
    """
    vm.import_("_fstring")
    vm.import_("strbuilder")

    w_format1 = vm.lookup_global(FQN("_fstring::format1"))
    n = len(args_wam)
    func_args: list[ast.FuncArg] = []
    params: list[FuncParam] = []
    body: list[ast.Stmt] = []

    wam_None = vm.wrap(None)
    for i, wam in enumerate(args_wam):
        loc = wam.loc
        w_T = wam.w_static_T
        arg_name = f"arg{i}"
        func_args.append(
            ast.FuncArg(loc, arg_name, ast.FQNConst(loc, w_T.fqn), "simple")
        )
        params.append(FuncParam(w_T, "simple"))

        # s{i} = format1[T_i, None, None](arg{i})
        s_name = f"s{i}"
        w_impl = vm.getitem_w(w_format1, w_T, wam_None, wam_None)
        assert isinstance(w_impl, W_Func)
        body.append(
            ast.Assign(
                loc=loc,
                target=ast.SingleTarget(loc, ast.StrLiteral(loc, s_name)),
                value=ast.Call(
                    loc=loc,
                    func=ast.FQNConst(loc, w_impl.fqn),
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
            args=[ast.Name(loc, f"s{i}")],
        )
        for i in range(n)
    ]
    capacity: ast.Expr
    if not lens:
        capacity = ast.Literal(loc, 0)
    else:
        capacity = lens[0]
        for l in lens[1:]:
            capacity = ast.BinOp(loc, "+", capacity, l)

    # sb = StrBuilder(capacity)
    w_StrBuilder = vm.lookup_global(FQN("strbuilder::StrBuilder"))
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
    for i in range(n):
        body.append(
            ast.StmtExpr(
                loc=loc,
                value=ast.CallMethod(
                    loc=loc,
                    target=ast.Name(loc, "sb"),
                    method=ast.StrLiteral(loc, "append"),
                    args=[ast.Name(loc, f"s{i}")],
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
    return W_OpSpec(w_func, args_wam)
