from typing import TYPE_CHECKING, Literal, NoReturn, Optional

from spy.analyze.symtable import Color
from spy.errors import SPyError
from spy.location import Loc
from spy.vm.exc import W_TypeError
from spy.vm.function import FuncParam, W_Func, W_FuncType
from spy.vm.modules.operator.convop import CONVERT_maybe
from spy.vm.object import W_Type
from spy.vm.opimpl import ArgSpec, W_OpImpl
from spy.vm.opspec import W_MetaArg, W_OpSpec

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

# DispatchKind is a property of an OPERATOR and can be:
#
#   - 'single' if the opspec depends only on the type of the first operand
#     (e.g., CALL, GETATTR, etc.)
#
#   - 'multi' is the opspec depends on the types of all operands (e.g., all
#     binary operators)
DispatchKind = Literal["single", "multi"]


def maybe_plural(n: int, singular: str, plural: Optional[str] = None) -> str:
    if n == 1:
        return singular
    elif plural is None:
        return singular + "s"
    else:
        return plural


def typecheck_opspec(
    vm: "SPyVM",
    w_opspec: W_OpSpec,
    in_args_wam: list[W_MetaArg],
    *,
    dispatch: DispatchKind,
    errmsg: str,
) -> W_OpImpl:
    """
    Turn the W_OpSpec into a W_OpImpl, ready to be execute()d.

    Check the arg types that we are passing to the OpSpec, and insert
    appropriate type conversions if needed.

    `dispatch` is used only for diagnostics: if it's 'single' we will
    report the type of the first operand, else of all operands.
    """
    if w_opspec.is_null():
        _opspec_null_error(in_args_wam, dispatch, errmsg)

    if w_opspec.is_const():
        assert w_opspec._w_const is not None
        return W_OpImpl.const(vm, w_opspec._w_const)

    assert w_opspec._w_func is not None

    # the final goal is to create an OpImpl which:
    #   - when executed behaves like a function of type w_in_functype
    #   - calls a function of type w_out_functype
    w_out_functype = w_opspec.w_functype
    w_in_functype = functype_from_opargs(
        in_args_wam, w_out_functype.w_restype, color=w_out_functype.color
    )

    # if it's a simple OpSpec, we automatically pass the in_args_wam in order
    if w_opspec.is_simple():
        out_args_wam = in_args_wam
    else:
        assert w_opspec._args_wam is not None
        out_args_wam = w_opspec._args_wam

    # if it's a direct call, we can display extra info about call location
    def_loc = w_opspec._w_func.def_loc
    call_loc = None
    if w_opspec.is_direct_call:
        wam_func = in_args_wam[0]
        call_loc = wam_func.loc

    # check that the number of arguments match
    got_nargs = len(out_args_wam)
    exp_nargs = len(w_out_functype.params)
    if not w_out_functype.is_argcount_ok(got_nargs):
        _call_error_wrong_argcount(
            got_nargs, exp_nargs, out_args_wam, def_loc=def_loc, call_loc=call_loc
        )

    # build the argspec for the W_OpImpl
    args = []
    for param, wam_out_arg in zip(w_out_functype.all_params(), out_args_wam):
        if w_out_functype.color == "blue" and wam_out_arg.color == "red":
            msg = "cannot call blue function with red arguments"
            err = SPyError("W_TypeError", msg)
            if call_loc:
                err.add("error", "this is blue", call_loc)
            err.add("error", "this is red", wam_out_arg.loc)
            if def_loc:
                err.add("note", "function defined here", def_loc)
            raise err

        # add a converter if needed (this might raise W_TypeError)
        w_conv = get_w_conv(vm, param.w_T, wam_out_arg, def_loc)
        arg: ArgSpec
        if wam_out_arg.is_blue():
            arg = ArgSpec.Const(wam_out_arg.w_blueval, wam_out_arg.loc)
        else:
            # red W_MetaArg MUST come from in_args_wam
            i = in_args_wam.index(wam_out_arg)
            arg = ArgSpec.Arg(i)

        if w_conv:
            arg = ArgSpec.Convert(w_conv, arg)
        args.append(arg)

    # everything good!
    w_opimpl = W_OpImpl(w_in_functype, w_opspec._w_func, args)
    return w_opimpl


def functype_from_opargs(
    args_wam: list[W_MetaArg], w_restype: W_Type, color: Color
) -> W_FuncType:
    params = [FuncParam(wam.w_static_T, "simple") for wam in args_wam]
    return W_FuncType.new(params, w_restype, color=color)


def get_w_conv(
    vm: "SPyVM", w_type: W_Type, wam_arg: W_MetaArg, def_loc: Optional[Loc]
) -> Optional[W_Func]:
    """
    Like CONVERT_maybe, but improve the error message if we can
    """
    try:
        return CONVERT_maybe(vm, w_type, wam_arg)
    except SPyError as err:
        if not err.match(W_TypeError):
            raise
        if def_loc:
            err.add("note", "function defined here", def_loc)
        raise


def _opspec_null_error(
    in_args_wam: list[W_MetaArg], dispatch: DispatchKind, errmsg: str
) -> NoReturn:
    """
    We couldn't find an OpSpec for this OPERATOR.
    The details of the error message depends on the DispatchKind:

     - single dispatch means that the target (argument 0) doesn't
       support this operation, so we report its type and its definition

     - multi dispatch means that all the types are equally imporant in
       determining whether an operation is supported, so we report all
       of them
    """
    typenames = [wam.w_static_T.fqn.human_name for wam in in_args_wam]
    errmsg = errmsg.format(*typenames)
    err = SPyError("W_TypeError", errmsg)
    if dispatch == "single":
        wam_target = in_args_wam[0]
        t = wam_target.w_static_T.fqn.human_name
        if wam_target.loc:
            err.add("error", f"this is `{t}`", wam_target.loc)
        if wam_target.sym:
            sym = wam_target.sym
            err.add("note", f"`{sym.name}` defined here", sym.loc)
    else:
        for wam_arg in in_args_wam:
            t = wam_arg.w_static_T.fqn.human_name
            err.add("error", f"this is `{t}`", wam_arg.loc)
    raise err


def _call_error_wrong_argcount(
    got: int,
    exp: int,
    args_wam: list[W_MetaArg],
    *,
    def_loc: Optional[Loc],
    call_loc: Optional[Loc],
) -> NoReturn:
    assert got != exp
    takes = maybe_plural(exp, f"takes {exp} argument")
    supplied = maybe_plural(
        got, f"1 argument was supplied", f"{got} arguments were supplied"
    )
    err = SPyError("W_TypeError", f"this function {takes} but {supplied}")
    #
    # if we know the call_loc, we can add more detailed errors
    if call_loc:
        if got < exp:
            diff = exp - got
            arguments = maybe_plural(diff, "argument")
            err.add("error", f"{diff} {arguments} missing", call_loc)
        else:
            diff = got - exp
            arguments = maybe_plural(diff, "argument")
            first_extra_loc = args_wam[exp].loc
            last_extra_loc = args_wam[-1].loc
            assert first_extra_loc is not None
            assert last_extra_loc is not None
            # XXX this assumes that all the arguments are on the same line
            loc = first_extra_loc.replace(col_end=last_extra_loc.col_end)
            err.add("error", f"{diff} extra {arguments}", loc)
    #
    if def_loc:
        err.add("note", "function defined here", def_loc)
    raise err
