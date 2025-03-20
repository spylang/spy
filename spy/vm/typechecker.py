from typing import TYPE_CHECKING, Optional, NoReturn, Any, Sequence, Literal
from types import NoneType
from spy import ast
from spy.irgen.symtable import Symbol, Color
from spy.errors import SPyTypeError, SPyNameError
from spy.location import Loc
from spy.vm.modules.operator.convop import CONVERT_maybe
from spy.vm.object import W_Object, W_Type
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.function import W_ASTFunc, W_Func, W_FuncType, FuncParam
from spy.vm.func_adapter import W_FuncAdapter, ArgSpec
from spy.vm.b import B
from spy.vm.modules.operator import OP, OP_from_token
from spy.util import magic_dispatch
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

# DispatchKind is a property of an OPERATOR and can be:
#
#   - 'single' if the opimpl depends only on the type of the first operand
#     (e.g., CALL, GETATTR, etc.)
#
#   - 'multi' is the opimpl depends on the types of all operands (e.g., all
#     binary operators)
DispatchKind = Literal['single', 'multi']

def maybe_plural(n: int, singular: str, plural: Optional[str] = None) -> str:
    if n == 1:
        return singular
    elif plural is None:
        return singular + 's'
    else:
        return plural


def typecheck_opimpl(
        vm: 'SPyVM',
        w_opimpl: W_OpImpl,
        in_args_wop: list[W_OpArg],
        *,
        dispatch: DispatchKind,
        errmsg: str,
) -> W_Func:
    """
    Turn the W_OpImpl into a W_Func which can be called using fast_call.

    Check the arg types that we are passing to the opimpl, and insert
    appropriate type conversions if needed.

    `dispatch` is used only for diagnostics: if it's 'single' we will
    report the type of the first operand, else of all operands.
    """
    if w_opimpl.is_null():
        _opimpl_null_error(in_args_wop, dispatch, errmsg)
    assert w_opimpl._w_func is not None

    # the want to make an adapter that:
    #   - behaves like a function of type w_in_functype
    #   - calls an opimpl of type w_out_functype
    w_out_functype = w_opimpl.w_functype
    w_in_functype = functype_from_opargs(
        in_args_wop,
        w_out_functype.w_restype,
        color=w_out_functype.color
    )

    # if it's a simple OpImpl, we automatically pass the in_args_wop in order
    if w_opimpl.is_simple():
        out_args_wop = in_args_wop
    else:
        assert w_opimpl._args_wop is not None
        out_args_wop = w_opimpl._args_wop

    # if it's a direct call, we can display extra info about call location
    def_loc = w_opimpl._w_func.def_loc
    call_loc = None
    if w_opimpl.is_direct_call:
        wop_func = in_args_wop[0]
        call_loc = wop_func.loc

    # check that the number of arguments match
    got_nargs = len(out_args_wop)
    exp_nargs = len(w_out_functype.params)
    if not w_out_functype.is_argcount_ok(got_nargs):
        _call_error_wrong_argcount(
            got_nargs,
            exp_nargs,
            out_args_wop,
            def_loc = def_loc,
            call_loc = call_loc)

    # build the argspec for the W_FuncAdapter
    args = []
    for param, wop_out_arg in zip(w_out_functype.all_params(), out_args_wop):
        # add a converter if needed (this might raise SPyTypeError)
        w_conv = get_w_conv(vm, param.w_type, wop_out_arg, def_loc)
        arg: ArgSpec
        if wop_out_arg.is_blue():
            arg = ArgSpec.Const(wop_out_arg.w_blueval, wop_out_arg.loc)
        else:
            # red W_OpArg MUST come from in_args_wop
            i = in_args_wop.index(wop_out_arg)
            arg = ArgSpec.Arg(i)

        if w_conv:
            arg = ArgSpec.Convert(w_conv, arg)
        args.append(arg)

    # everything good!
    w_adapter = W_FuncAdapter(w_in_functype, w_opimpl._w_func, args)
    return w_adapter


def functype_from_opargs(args_wop: list[W_OpArg], w_restype: W_Type,
                         color: Color) -> W_FuncType:
    params = [
        FuncParam(f'v{i}', wop.w_static_type, 'simple')
        for i, wop in enumerate(args_wop)
    ]
    return W_FuncType.new(params, w_restype, color=color)


def get_w_conv(vm: 'SPyVM', w_type: W_Type, wop_arg: W_OpArg,
               def_loc: Optional[Loc]) -> Optional[W_Func]:
    """
    Like CONVERT_maybe, but improve the error message if we can
    """
    try:
        return CONVERT_maybe(vm, w_type, wop_arg)
    except SPyTypeError as err:
        if def_loc:
            err.add('note', 'function defined here', def_loc)
        raise


def _opimpl_null_error(
        in_args_wop: list[W_OpArg],
        dispatch: DispatchKind,
        errmsg: str
) -> NoReturn:
    """
    We couldn't find an OpImpl for this OPERATOR.
    The details of the error message depends on the DispatchKind:

     - single dispatch means that the target (argument 0) doesn't
       support this operation, so we report its type and its definition

     - multi dispatch means that all the types are equally imporant in
       determining whether an operation is supported, so we report all
       of them
    """
    typenames = [wop.w_static_type.fqn.human_name for wop in in_args_wop]
    errmsg = errmsg.format(*typenames)
    err = SPyTypeError(errmsg)
    if dispatch == 'single':
        wop_target = in_args_wop[0]
        t = wop_target.w_static_type.fqn.human_name
        if wop_target.loc:
            err.add('error', f'this is `{t}`', wop_target.loc)
        if wop_target.sym:
            sym = wop_target.sym
            err.add('note', f'`{sym.name}` defined here', sym.loc)
    else:
        for wop_arg in in_args_wop:
            t = wop_arg.w_static_type.fqn.human_name
            err.add('error', f'this is `{t}`', wop_arg.loc)
    raise err


def _call_error_wrong_argcount(
        got: int, exp: int,
        args_wop: list[W_OpArg],
        *,
        def_loc: Optional[Loc],
        call_loc: Optional[Loc],
) -> NoReturn:
    assert got != exp
    takes = maybe_plural(exp, f'takes {exp} argument')
    supplied = maybe_plural(got,
                            f'1 argument was supplied',
                            f'{got} arguments were supplied')
    err = SPyTypeError(f'this function {takes} but {supplied}')
    #
    # if we know the call_loc, we can add more detailed errors
    if call_loc:
        if got < exp:
            diff = exp - got
            arguments = maybe_plural(diff, 'argument')
            err.add('error', f'{diff} {arguments} missing', call_loc)
        else:
            diff = got - exp
            arguments = maybe_plural(diff, 'argument')
            first_extra_loc = args_wop[exp].loc
            last_extra_loc = args_wop[-1].loc
            assert first_extra_loc is not None
            assert last_extra_loc is not None
            # XXX this assumes that all the arguments are on the same line
            loc = first_extra_loc.replace(
                col_end = last_extra_loc.col_end
            )
            err.add('error', f'{diff} extra {arguments}', loc)
    #
    if def_loc:
        err.add('note', 'function defined here', def_loc)
    raise err
