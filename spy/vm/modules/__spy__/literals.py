"""
Implementation of list and dict literals.
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

    The astcompiler desugars:
        [a, b, c]  ==>   __spy__::list_literal(a, b, c)

    Here we generate a @force_inline impl which creates the list by calling
    `list[T]::new` and `list[T]::_push`.

    The empty list `[]` is special: it is the `__spy__::empty_list` singleton, which is
    converted to the right list type by `__convert_from__`.

    Ideally, we would like to implement it at applevel, but we cannot until we have
    `unroll()`.
    """
    if len(args_wam) == 0:
        return W_OpSpec.const(SPY.w_empty_list)

    # unify the type of all the items
    w_itemtype = args_wam[0].w_static_T
    for wam in args_wam[1:]:
        w_itemtype = vm.union_type(w_itemtype, wam.w_static_T)

    w_ListType = vm.lookup_global(FQN("_list::list"))
    w_T = vm.getitem_w(w_ListType, w_itemtype, loc=args_wam[0].loc)  # list[i32]
    assert isinstance(w_T, W_Type)
    w_push = vm.lookup_global(w_T.fqn.join("_push"))
    fqn_T = vm.make_fqn_const(w_T)
    fqn_push = vm.make_fqn_const(w_push)

    loc = Loc.here()
    args = [ast.Name(wam.loc, f"arg{i}") for i, wam in enumerate(args_wam)]
    body: ast.Expr = ast.Call(loc, ast.FQNConst(loc, fqn_T), [])
    for arg in args:
        body = ast.Call(arg.loc, ast.FQNConst(arg.loc, fqn_push), [body, arg])

    return make_literal_opspec(vm, "list_literal", args_wam, args, w_T, body)


@SPY.builtin_func(color="blue", kind="metafunc")
def w_dict_literal(vm: "SPyVM", *args_wam: W_MetaArg) -> W_OpSpec:
    """
    Interp-level implementation of dict literals.

    The astcompiler desugars:
        {a: 1, b: 2}  ==>   __spy__::dict_literal(a, 1, b, 2)

    Here we generate a @force_inline impl which creates the list by calling
    `dict[K, V]::new` and `dict[K, V]::_push`.

    The empty dict `{}` is special: it is the `__spy__::empty_dict` singleton, which
    is converted to the right dict type by `__convert_from__`.

    Ideally, we would like to implement it at applevel, but we cannot until we have
    `unroll()`.
    """
    if len(args_wam) == 0:
        return W_OpSpec.const(SPY.w_empty_dict)
    assert len(args_wam) % 2 == 0

    # unify the types of the keys and the values
    keys_wam = args_wam[0::2]
    values_wam = args_wam[1::2]
    w_keytype = keys_wam[0].w_static_T
    w_valuetype = values_wam[0].w_static_T
    for wam_key, wam_value in zip(keys_wam[1:], values_wam[1:]):
        w_keytype = vm.union_type(w_keytype, wam_key.w_static_T)
        w_valuetype = vm.union_type(w_valuetype, wam_value.w_static_T)

    w_DictType = vm.lookup_global(FQN("_dict::dict"))
    w_T = vm.getitem_w(w_DictType, w_keytype, w_valuetype)  # dict[K, V]
    assert isinstance(w_T, W_Type)
    w_push = vm.lookup_global(w_T.fqn.join("_push"))
    fqn_T = vm.make_fqn_const(w_T)
    fqn_push = vm.make_fqn_const(w_push)

    loc = Loc.here()
    args = [ast.Name(wam.loc, f"arg{i}") for i, wam in enumerate(args_wam)]
    body: ast.Expr = ast.Call(loc, ast.FQNConst(loc, fqn_T), [])
    for key, value in zip(args[0::2], args[1::2]):
        body = ast.Call(key.loc, ast.FQNConst(key.loc, fqn_push), [body, key, value])

    return make_literal_opspec(vm, "dict_literal", args_wam, args, w_T, body)


def make_literal_opspec(
    vm: "SPyVM",
    name: str,
    args_wam: tuple[W_MetaArg, ...],
    args: list[ast.Name],
    w_T: W_Type,
    body: ast.Expr,
) -> W_OpSpec:
    """
    Small helper to reduce code duplication between list_literal and dict_literal:
    synthesize a force-inline ASTFunc which takes all the args_wam as parameters
    and returns a `w_T`:

        @force_inline
        def impl(arg0: T0, arg1: T1, ...) -> w_T:
            return <body>

    `args` are the names of the parameters, as `ast.Name` nodes: `body` is
    supposed to refer to them.
    """
    loc = Loc.here()
    func_args: list[ast.FuncArg] = []
    params: list[FuncParam] = []
    for wam, arg in zip(args_wam, args):
        w_argT = wam.w_static_T
        func_args.append(
            ast.FuncArg(
                wam.loc,
                arg.id,
                ast.FQNConst(wam.loc, vm.make_fqn_const(w_argT)),
                "simple",
            )
        )
        params.append(FuncParam(w_argT, "simple"))

    funcdef = ast.FuncDef(
        loc=loc,
        stage="astcompiled",
        color="red",
        kind="plain",
        name=name,
        args=func_args,
        return_type=ast.FQNConst(loc, vm.make_fqn_const(w_T)),
        defaults=[],
        docstring=None,
        scoping_rules="pythonic",
        body=ast.Block(loc=loc, body=[ast.Return(loc, body)]),
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
    funcdef = module.get_funcdef(name)
    fqn = vm.get_unique_FQN(FQN(f"__spy__::{name}::impl"))
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
