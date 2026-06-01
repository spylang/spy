"""
Second half of the `builtins` module.

The first half is in vm/b.py. See its docstring for more details.
"""

from typing import TYPE_CHECKING

from spy import ast
from spy.analyze.scope import ScopeAnalyzer
from spy.errors import SPyError
from spy.fqn import FQN
from spy.location import Loc
from spy.vm.b import BUILTINS, TYPES, B
from spy.vm.function import FuncParam, W_ASTFunc, W_Func, W_FuncType
from spy.vm.modules.__spy__ import SPY
from spy.vm.modules.__spy__.interp_list import (
    W_StrInterpList,
    make_str_interp_list,
    w_str_interp_list_type,
)
from spy.vm.object import W_Object, W_Type
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.primitive import W_F64, W_I8, W_I32, W_U8, W_Bool
from spy.vm.str import W_Str

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@BUILTINS.builtin_func(color="blue", kind="metafunc")
def w_STATIC_TYPE(vm: "SPyVM", wam_obj: W_MetaArg) -> W_OpSpec:
    return W_OpSpec.const(wam_obj.w_static_T)


@BUILTINS.builtin_func(color="blue", kind="metafunc")
def w_print(vm: "SPyVM", *args_wam: W_MetaArg) -> W_OpSpec:
    vm.import_("_print")
    w_print1 = vm.lookup_global(FQN("_print::print1"))
    w_println = vm.lookup_global(FQN("_print::println"))

    # Blue args are eagerly str()'d so that e.g. `print(int)` works even when
    # the type isn't supported by the C backend. Non-last args use print1[T];
    # the last arg uses println[T].
    new_args_wam: list[W_MetaArg] = []
    for wam in args_wam:
        if wam.color == "blue":
            wam_s = vm.str_wam(wam, loc=wam.loc)
            if wam_s.color != "blue":
                wam_s = W_MetaArg.from_w_obj(vm, wam_s.w_val, loc=wam.loc)
            new_args_wam.append(wam_s)
        else:
            new_args_wam.append(wam)

    if len(new_args_wam) == 0:
        # print() with no args: equivalent to println("")
        new_args_wam.append(W_MetaArg.from_w_obj(vm, vm.wrap("")))

    if len(new_args_wam) == 1:
        # single arg: equivalent to println[T](arg)
        wam = new_args_wam[0]
        w_impl = vm.getitem_w(w_println, wam.w_static_T)
        assert isinstance(w_impl, W_Func)
        return W_OpSpec(w_impl, [wam])

    # generic case: for e.g. print(a, b, c) we synthesise an ASTFunc like this:
    #     @force_inline
    #     def impl(a: T1, b: T2, c: T3) -> None:
    #         print1[T1](a)
    #         print1[T2](b)
    #         println[T3](c)
    func_args: list[ast.FuncArg] = []
    params: list[FuncParam] = []
    body: list[ast.Stmt] = []
    n = len(new_args_wam)
    for i, wam in enumerate(new_args_wam):
        loc = wam.loc
        w_T = wam.w_static_T
        arg_name = f"arg{i}"
        func_args.append(
            ast.FuncArg(loc, arg_name, ast.FQNConst(loc, w_T.fqn), "simple")
        )
        params.append(FuncParam(w_T, "simple"))
        # print1[T] for non-last args; println[T] for the last one
        w_print_func = w_println if i == n - 1 else w_print1
        w_impl = vm.getitem_w(w_print_func, w_T)
        assert isinstance(w_impl, W_Func)
        body.append(
            ast.StmtExpr(
                loc,
                ast.Call(
                    loc,
                    ast.FQNConst(loc, w_impl.fqn),
                    [ast.Name(loc, arg_name)],
                ),
            )
        )

    loc = Loc.here()
    body.append(ast.Return(loc, ast.Constant(loc, None)))

    fqn = FQN("_print::print::impl")
    fqn = vm.get_unique_FQN(fqn)
    funcdef = ast.FuncDef(
        loc=loc,
        color="red",
        kind="plain",
        name="print",
        args=func_args,
        return_type=ast.FQNConst(loc, TYPES.w_NoneType.fqn),
        defaults=[],
        docstring=None,
        body=body,
        decorators=[],
    )
    module = ast.Module(
        loc=loc,
        filename="<generated>",
        docstring=None,
        decls=[ast.GlobalFuncDef(loc, funcdef)],
    )
    ScopeAnalyzer("_print", module).analyze()
    w_functype = W_FuncType.new(params, w_restype=TYPES.w_NoneType)
    w_func = W_ASTFunc(
        w_functype,
        fqn,
        funcdef,
        closure=(),
        defaults_w=[],
        lowering_stage="source",
        is_force_inline=True,
    )
    vm.add_global(fqn, w_func)
    return W_OpSpec(w_func, new_args_wam)


@BUILTINS.builtin_func(color="blue", kind="metafunc")
def w_len(vm: "SPyVM", wam_obj: W_MetaArg) -> W_OpSpec:
    w_T = wam_obj.w_static_T
    if w_fn := w_T.lookup_func(vm, "__len__"):
        w_opspec = vm.fast_metacall(w_fn, [wam_obj])
        return w_opspec

    t = w_T.fqn.human_name(vm)
    raise SPyError.simple(
        "W_TypeError", f"cannot call len(`{t}`)", f"this is `{t}`", wam_obj.loc
    )


@BUILTINS.builtin_func(color="blue", kind="metafunc")
def w_repr(vm: "SPyVM", wam_obj: W_MetaArg) -> W_OpSpec:
    w_T = wam_obj.w_static_T
    if w_fn := w_T.lookup_func(vm, "__repr__"):
        w_opspec = vm.fast_metacall(w_fn, [wam_obj])
        return w_opspec

    # this can happen only if you override a __repr__ which returns
    # OpSpec.NULL
    t = w_T.fqn.human_name(vm)
    raise SPyError.simple(
        "W_TypeError", f"cannot call repr(`{t}`)", f"this is `{t}`", wam_obj.loc
    )


@BUILTINS.builtin_func
def w_hash_i8(vm: "SPyVM", w_x: W_I8) -> W_I32:
    x = vm.unwrap_i8(w_x)
    if x == -1:
        return vm.wrap(2)
    return vm.wrap(x)


@BUILTINS.builtin_func
def w_hash_i32(vm: "SPyVM", w_x: W_I32) -> W_I32:
    if (vm.unwrap_i32(w_x)) == -1:
        return vm.wrap(2)
    return w_x


@BUILTINS.builtin_func
def w_hash_u8(vm: "SPyVM", w_x: W_U8) -> W_I32:
    return vm.wrap(vm.unwrap_u8(w_x))


@BUILTINS.builtin_func
def w_hash_bool(vm: "SPyVM", w_x: W_Bool) -> W_I32:
    if w_x is B.w_False:
        return vm.wrap(0)
    elif w_x is B.w_True:
        return vm.wrap(1)
    else:
        assert False, "unreachable"


@BUILTINS.builtin_func
def w_hash_str(vm: "SPyVM", w_x: W_Str) -> W_I32:
    assert isinstance(w_x, W_Str)
    res = vm.ll.call("spy_str_hash", w_x.ptr)
    return vm.wrap(res)


@BUILTINS.builtin_func(color="blue", kind="metafunc")
def w_hash(vm: "SPyVM", wam_obj: W_MetaArg) -> W_OpSpec:
    w_T = wam_obj.w_static_T
    if w_T is B.w_i8:
        return W_OpSpec(B.w_hash_i8)
    elif w_T is B.w_i32:
        return W_OpSpec(B.w_hash_i32)
    elif w_T is B.w_u8:
        return W_OpSpec(B.w_hash_u8)
    elif w_T is B.w_bool:
        return W_OpSpec(B.w_hash_bool)
    elif w_T is B.w_str:
        return W_OpSpec(B.w_hash_str)

    if w_fn := w_T.lookup_func(vm, "__hash__"):
        w_opspec = vm.fast_metacall(w_fn, [wam_obj])
        return w_opspec

    t = w_T.fqn.human_name(vm)
    raise SPyError.simple(
        "W_TypeError", f"unhashable type '{t}'", f"this is `{t}`", wam_obj.loc
    )


# w_dir is a metafunc because we can precompute the result at blue time
@BUILTINS.builtin_func(color="blue", kind="metafunc")
def w_dir(vm: "SPyVM", wam_obj: W_MetaArg) -> W_OpSpec:
    # get the names from the type
    w_T = wam_obj.w_static_T
    names = w_T.spy_dir(vm)

    # get the names from the instance, if it's blue
    if wam_obj.color == "blue":
        new_names = wam_obj.w_blueval.spy_dir(vm)
        names.update(new_names)

    names_w = [vm.wrap(name) for name in sorted(names)]
    w_names = make_str_interp_list(names_w)
    return W_OpSpec.const(w_names)


@BUILTINS.builtin_func(color="blue", kind="metafunc")
def w_getattr(vm: "SPyVM", wam_obj: W_MetaArg, wam_name: W_MetaArg) -> W_OpSpec:
    # ensure that wam_name is blue; raise TypeError if not
    name = wam_name.blue_unwrap_str(vm)

    @vm.register_builtin_func("builtins", "getattr", [name])
    def w_fn(vm: "SPyVM", w_obj: W_Object, w_name: W_Str) -> W_Object:
        assert False, (
            "this function shouldn't be called, it's special cased by astframe"
        )

    return W_OpSpec(w_fn)


@BUILTINS.builtin_func(color="blue", kind="metafunc")
def w_hasattr(vm: "SPyVM", wam_obj: W_MetaArg, wam_name: W_MetaArg) -> W_OpSpec:
    # ensure that wam_name is blue; raise TypeError if not
    name = wam_name.blue_unwrap_str(vm)

    @vm.register_builtin_func("builtins", "hasattr", [name])
    def w_fn(vm: "SPyVM", w_obj: W_Object, w_name: W_Str) -> W_Object:
        assert False, (
            "this function shouldn't be called, it's special cased by astframe"
        )

    return W_OpSpec(w_fn)


@BUILTINS.builtin_func(color="blue", kind="metafunc")
def w_setattr(
    vm: "SPyVM", wam_obj: W_MetaArg, wam_name: W_MetaArg, wam_value: W_MetaArg
) -> W_OpSpec:
    # ensure that wam_name is blue; raise TypeError if not
    name = wam_name.blue_unwrap_str(vm)

    @vm.register_builtin_func("builtins", "setattr", [name])
    def w_fn(vm: "SPyVM", w_obj: W_Object, w_name: W_Str, w_val: W_Object) -> W_Object:
        assert False, (
            "this function shouldn't be called, it's special cased by astframe"
        )

    return W_OpSpec(w_fn)


# add aliases for common types. For now we map:
#   int -> i32
#   float -> f64
#
# We might want to map int to different concrete types, depending on the
# platform? Or maybe have some kind of "configure step"?
BUILTINS.add("int", BUILTINS.w_i32)
BUILTINS.add("float", BUILTINS.w_f64)
BUILTINS.add("complex", BUILTINS.w_complex128)
