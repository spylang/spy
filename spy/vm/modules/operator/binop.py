from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.object import W_Type
from spy.vm.opspec import W_OpSpec, W_MetaArg
from spy.vm.opimpl import W_OpImpl
from . import OP
from .multimethod import MultiMethodTable
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

MM = MultiMethodTable()

# i8 ops
MM.register("+",  "i8", "i8", OP.w_i8_add)
MM.register("-",  "i8", "i8", OP.w_i8_sub)
MM.register("*",  "i8", "i8", OP.w_i8_mul)
MM.register("/",  "i8", "i8", OP.w_i8_div)
MM.register("//", "i8", "i8", OP.w_i8_floordiv)
MM.register("%",  "i8", "i8", OP.w_i8_mod)
MM.register("<<", "i8", "i8", OP.w_i8_lshift)
MM.register(">>", "i8", "i8", OP.w_i8_rshift)
MM.register("&",  "i8", "i8", OP.w_i8_and)
MM.register("|",  "i8", "i8", OP.w_i8_or)
MM.register("^",  "i8", "i8", OP.w_i8_xor)
MM.register("==", "i8", "i8", OP.w_i8_eq)
MM.register("!=", "i8", "i8", OP.w_i8_ne)
MM.register("<" , "i8", "i8", OP.w_i8_lt)
MM.register("<=", "i8", "i8", OP.w_i8_le)
MM.register(">" , "i8", "i8", OP.w_i8_gt)
MM.register(">=", "i8", "i8", OP.w_i8_ge)

# u8 ops
MM.register("+",  "u8", "u8", OP.w_u8_add)
MM.register("-",  "u8", "u8", OP.w_u8_sub)
MM.register("*",  "u8", "u8", OP.w_u8_mul)
MM.register("/",  "u8", "u8", OP.w_u8_div)
MM.register("//", "u8", "u8", OP.w_u8_floordiv)
MM.register("%",  "u8", "u8", OP.w_u8_mod)
MM.register("<<", "u8", "u8", OP.w_u8_lshift)
MM.register(">>", "u8", "u8", OP.w_u8_rshift)
MM.register("&",  "u8", "u8", OP.w_u8_and)
MM.register("|",  "u8", "u8", OP.w_u8_or)
MM.register("^",  "u8", "u8", OP.w_u8_xor)
MM.register("==", "u8", "u8", OP.w_u8_eq)
MM.register("!=", "u8", "u8", OP.w_u8_ne)
MM.register("<" , "u8", "u8", OP.w_u8_lt)
MM.register("<=", "u8", "u8", OP.w_u8_le)
MM.register(">" , "u8", "u8", OP.w_u8_gt)
MM.register(">=", "u8", "u8", OP.w_u8_ge)

# i32 ops
MM.register("+",  "i32", "i32", OP.w_i32_add)
MM.register("-",  "i32", "i32", OP.w_i32_sub)
MM.register("*",  "i32", "i32", OP.w_i32_mul)
MM.register("/",  "i32", "i32", OP.w_i32_div)
MM.register("//", "i32", "i32", OP.w_i32_floordiv)
MM.register("%",  "i32", "i32", OP.w_i32_mod)
MM.register("<<", "i32", "i32", OP.w_i32_lshift)
MM.register(">>", "i32", "i32", OP.w_i32_rshift)
MM.register("&",  "i32", "i32", OP.w_i32_and)
MM.register("|",  "i32", "i32", OP.w_i32_or)
MM.register("^",  "i32", "i32", OP.w_i32_xor)
MM.register("==", "i32", "i32", OP.w_i32_eq)
MM.register("!=", "i32", "i32", OP.w_i32_ne)
MM.register("<" , "i32", "i32", OP.w_i32_lt)
MM.register("<=", "i32", "i32", OP.w_i32_le)
MM.register(">" , "i32", "i32", OP.w_i32_gt)
MM.register(">=", "i32", "i32", OP.w_i32_ge)

# f64 ops
MM.register("+",  "f64", "f64", OP.w_f64_add)
MM.register("-",  "f64", "f64", OP.w_f64_sub)
MM.register("*",  "f64", "f64", OP.w_f64_mul)
MM.register("/",  "f64", "f64", OP.w_f64_div)
MM.register("//", "f64", "f64", OP.w_f64_floordiv)
MM.register("%",  "f64", "f64", OP.w_f64_mod)
MM.register("==", "f64", "f64", OP.w_f64_eq)
MM.register("!=", "f64", "f64", OP.w_f64_ne)
MM.register("<" , "f64", "f64", OP.w_f64_lt)
MM.register("<=", "f64", "f64", OP.w_f64_le)
MM.register(">" , "f64", "f64", OP.w_f64_gt)
MM.register(">=", "f64", "f64", OP.w_f64_ge)

# mixed int/f64 ops: this is still small enough that we can write it manually,
# but we should consider the idea of generating this table automatically. This
# will become especially relevant when we add more integer types.
for int_t in ("i8", "u8", "i32"):
    MM.register("+",  "f64", int_t, OP.w_f64_add)
    MM.register("+",  int_t, "f64", OP.w_f64_add)
    MM.register("-",  "f64", int_t, OP.w_f64_sub)
    MM.register("-",  int_t, "f64", OP.w_f64_sub)
    MM.register("*",  "f64", int_t, OP.w_f64_mul)
    MM.register("*",  int_t, "f64", OP.w_f64_mul)
    MM.register("/",  "f64", int_t, OP.w_f64_div)
    MM.register("/",  int_t, "f64", OP.w_f64_div)
    MM.register("==", "f64", int_t, OP.w_f64_eq)
    MM.register("==", int_t, "f64", OP.w_f64_eq)
    MM.register("!=", "f64", int_t, OP.w_f64_ne)
    MM.register("!=", int_t, "f64", OP.w_f64_ne)
    MM.register("<" , "f64", int_t, OP.w_f64_lt)
    MM.register("<" , int_t, "f64", OP.w_f64_lt)
    MM.register("<=", "f64", int_t, OP.w_f64_le)
    MM.register("<=", int_t, "f64", OP.w_f64_le)
    MM.register(">" , "f64", int_t, OP.w_f64_gt)
    MM.register(">" , int_t, "f64", OP.w_f64_gt)
    MM.register(">=", "f64", int_t, OP.w_f64_ge)
    MM.register(">=", int_t, "f64", OP.w_f64_ge)

# str ops
MM.register("+",  "str", "str", OP.w_str_add)
MM.register("*",  "str", "i32", OP.w_str_mul)
MM.register("==", "str", "str", OP.w_str_eq)
MM.register("!=", "str", "str", OP.w_str_ne)

# bool ops
MM.register("==", "bool", "bool", OP.w_bool_eq)
MM.register("!=", "bool", "bool", OP.w_bool_ne)
MM.register("&",  "bool", "bool", OP.w_bool_and)
MM.register("|",  "bool", "bool", OP.w_bool_or)
MM.register("^",  "bool", "bool", OP.w_bool_xor)
MM.register("<",  "bool", "bool", OP.w_bool_lt)
MM.register("<=", "bool", "bool", OP.w_bool_le)
MM.register(">",  "bool", "bool", OP.w_bool_gt)
MM.register(">=", "bool", "bool", OP.w_bool_ge)

# dynamic ops
MM.register_partial("+",  "dynamic", OP.w_dynamic_add)
MM.register_partial("*",  "dynamic", OP.w_dynamic_mul)
MM.register_partial("==", "dynamic", OP.w_dynamic_eq)
MM.register_partial("!=", "dynamic", OP.w_dynamic_ne)
MM.register_partial("<",  "dynamic", OP.w_dynamic_lt)
MM.register_partial("<=", "dynamic", OP.w_dynamic_le)
MM.register_partial(">",  "dynamic", OP.w_dynamic_gt)
MM.register_partial(">=", "dynamic", OP.w_dynamic_ge)


@OP.builtin_func(color="blue")
def w_ADD(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_ltype = wam_l.w_static_T
    if w_opspec := MM.get_binary_opspec("+", wam_l, wam_r):
        pass
    elif w_add := w_ltype.lookup_func("__add__"):
        w_opspec = vm.fast_metacall(w_add, [wam_l, wam_r])
    else:
        w_opspec = W_OpSpec.NULL
    return typecheck_opspec(vm, w_opspec, [wam_l, wam_r],
                            dispatch="multi",
                            errmsg="cannot do `{0}` + `{1}`")

@OP.builtin_func(color="blue")
def w_SUB(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_ltype = wam_l.w_static_T
    if w_opspec := MM.get_binary_opspec("-", wam_l, wam_r):
        pass
    elif w_sub := w_ltype.lookup_func("__sub__"):
        w_opspec = vm.fast_metacall(w_sub, [wam_l, wam_r])
    else:
        w_opspec = W_OpSpec.NULL
    return typecheck_opspec(vm, w_opspec, [wam_l, wam_r],
                            dispatch="multi",
                            errmsg="cannot do `{0}` - `{1}`")

@OP.builtin_func(color="blue")
def w_MUL(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_ltype = wam_l.w_static_T
    if w_opspec := MM.get_binary_opspec("*", wam_l, wam_r):
        pass
    elif w_mul := w_ltype.lookup_func("__mul__"):
        w_opspec = vm.fast_metacall(w_mul, [wam_l, wam_r])
    else:
        w_opspec = W_OpSpec.NULL
    return typecheck_opspec(vm, w_opspec, [wam_l, wam_r],
                            dispatch="multi",
                            errmsg="cannot do `{0}` * `{1}`")

@OP.builtin_func(color="blue")
def w_DIV(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_ltype = wam_l.w_static_T
    if w_opspec := MM.get_binary_opspec("/", wam_l, wam_r):
        pass
    elif w_div := w_ltype.lookup_func("__div__"):
        w_opspec = vm.fast_metacall(w_div, [wam_l, wam_r])
    else:
        w_opspec = W_OpSpec.NULL
    return typecheck_opspec(vm, w_opspec, [wam_l, wam_r],
                            dispatch="multi",
                            errmsg="cannot do `{0}` / `{1}`")

@OP.builtin_func(color="blue")
def w_FLOORDIV(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_ltype = wam_l.w_static_T
    if w_opspec := MM.get_binary_opspec("//", wam_l, wam_r):
        pass
    elif w_floordiv := w_ltype.lookup_func("__floordiv__"):
        w_opspec = vm.fast_metacall(w_floordiv, [wam_l, wam_r])
    else:
        w_opspec = W_OpSpec.NULL
    return typecheck_opspec(vm, w_opspec, [wam_l, wam_r],
                            dispatch="multi",
                            errmsg="cannot do `{0}` // `{1}`")


@OP.builtin_func(color="blue")
def w_MOD(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_ltype = wam_l.w_static_T
    if w_opspec := MM.get_binary_opspec("%", wam_l, wam_r):
        pass
    elif w_mod := w_ltype.lookup_func("__mod__"):
        w_opspec = vm.fast_metacall(w_mod, [wam_l, wam_r])
    else:
        w_opspec = W_OpSpec.NULL
    return typecheck_opspec(vm, w_opspec, [wam_l, wam_r],
                            dispatch="multi",
                            errmsg="cannot do `{0}` % `{1}`")

@OP.builtin_func(color="blue")
def w_LSHIFT(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_ltype = wam_l.w_static_T
    if w_opspec := MM.get_binary_opspec("<<", wam_l, wam_r):
        pass
    elif w_lshift := w_ltype.lookup_func("__lshift__"):
        w_opspec = vm.fast_metacall(w_lshift, [wam_l, wam_r])
    else:
        w_opspec = W_OpSpec.NULL
    return typecheck_opspec(vm, w_opspec, [wam_l, wam_r],
                            dispatch="multi",
                            errmsg="cannot do `{0}` << `{1}`")

@OP.builtin_func(color="blue")
def w_RSHIFT(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_ltype = wam_l.w_static_T
    if w_opspec := MM.get_binary_opspec(">>", wam_l, wam_r):
        pass
    elif w_rshift := w_ltype.lookup_func("__rshift__"):
        w_opspec = vm.fast_metacall(w_rshift, [wam_l, wam_r])
    else:
        w_opspec = W_OpSpec.NULL
    return typecheck_opspec(vm, w_opspec, [wam_l, wam_r],
                            dispatch="multi",
                            errmsg="cannot do `{0}` >> `{1}`")

@OP.builtin_func(color="blue")
def w_AND(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_ltype = wam_l.w_static_T
    if w_opspec := MM.get_binary_opspec("&", wam_l, wam_r):
        pass
    elif w_and := w_ltype.lookup_func("__and__"):
        w_opspec = vm.fast_metacall(w_and, [wam_l, wam_r])
    else:
        w_opspec = W_OpSpec.NULL
    return typecheck_opspec(vm, w_opspec, [wam_l, wam_r],
                            dispatch="multi",
                            errmsg="cannot do `{0}` & `{1}`")

@OP.builtin_func(color="blue")
def w_OR(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_ltype = wam_l.w_static_T
    if w_opspec := MM.get_binary_opspec("|", wam_l, wam_r):
        pass
    elif w_or := w_ltype.lookup_func("__or__"):
        w_opspec = vm.fast_metacall(w_or, [wam_l, wam_r])
    else:
        w_opspec = W_OpSpec.NULL
    return typecheck_opspec(vm, w_opspec, [wam_l, wam_r],
                            dispatch="multi",
                            errmsg="cannot do `{0}` | `{1}`")

@OP.builtin_func(color="blue")
def w_XOR(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_ltype = wam_l.w_static_T
    if w_opspec := MM.get_binary_opspec("^", wam_l, wam_r):
        pass
    elif w_xor := w_ltype.lookup_func("__xor__"):
        w_opspec = vm.fast_metacall(w_xor, [wam_l, wam_r])
    else:
        w_opspec = W_OpSpec.NULL
    return typecheck_opspec(vm, w_opspec, [wam_l, wam_r],
                            dispatch="multi",
                            errmsg="cannot do `{0}` ^ `{1}`")

def can_use_reference_eq(vm: "SPyVM", w_ltype: W_Type, w_rtype: W_Type) -> bool:
    """
    We can use 'is' to implement 'eq' if:
      1. the two types have a common ancestor
      2. the common ancestor must be a reference type
    """
    w_common = vm.union_type(w_ltype, w_rtype)
    return (
        w_common is not B.w_object and
        w_common is not B.w_dynamic and
        w_common.is_reference_type(vm)
    )

@OP.builtin_func(color="blue")
def w_EQ(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_ltype = wam_l.w_static_T
    w_rtype = wam_r.w_static_T
    if w_opspec := MM.get_binary_opspec("==", wam_l, wam_r):
        pass
    elif w_eq := w_ltype.lookup_func("__eq__"):
        w_opspec = vm.fast_metacall(w_eq, [wam_l, wam_r])
    elif can_use_reference_eq(vm, w_ltype, w_rtype):
        w_opspec = W_OpSpec(OP.w_object_is)
    else:
        w_opspec = W_OpSpec.NULL
    return typecheck_opspec(vm, w_opspec, [wam_l, wam_r],
                            dispatch="multi",
                            errmsg="cannot do `{0}` == `{1}`")

@OP.builtin_func(color="blue")
def w_NE(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_ltype = wam_l.w_static_T
    w_rtype = wam_r.w_static_T
    if w_opspec := MM.get_binary_opspec("!=", wam_l, wam_r):
        pass
    elif w_ne := w_ltype.lookup_func("__ne__"):
        w_opspec = vm.fast_metacall(w_ne, [wam_l, wam_r])
    elif can_use_reference_eq(vm, w_ltype, w_rtype):
        w_opspec = W_OpSpec(OP.w_object_isnot)
    else:
        w_opspec = W_OpSpec.NULL
    return typecheck_opspec(vm, w_opspec, [wam_l, wam_r],
                            dispatch="multi",
                            errmsg="cannot do `{0}` != `{1}`")

@OP.builtin_func(color="blue")
def w_UNIVERSAL_EQ(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    # XXX this seems wrong: if we do universal_eq(i32, i32), we should get the
    # same as eq(i32, i32), not "w_object_universal_eq". In practice, it's not
    # a problem for now, because it's not exposed to the user, and we use it
    # only on W_Objects.
    w_opspec = W_OpSpec(OP.w_object_universal_eq)
    return typecheck_opspec(vm, w_opspec, [wam_l, wam_r],
                            dispatch="multi",
                            errmsg="cannot do `{0}` <universal_eq> `{1}`")

@OP.builtin_func(color="blue")
def w_UNIVERSAL_NE(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    # XXX: see the commet in UNIVERSAL_EQ
    w_opspec = W_OpSpec(OP.w_object_universal_ne)
    return typecheck_opspec(vm, w_opspec, [wam_l, wam_r],
                            dispatch="multi",
                            errmsg="cannot do `{0}` <universal_ne> `{1}`")

@OP.builtin_func(color="blue")
def w_LT(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_ltype = wam_l.w_static_T
    if w_opspec := MM.get_binary_opspec("<", wam_l, wam_r):
        pass
    elif w_lt := w_ltype.lookup_func("__lt__"):
        w_opspec = vm.fast_metacall(w_lt, [wam_l, wam_r])
    else:
        w_opspec = W_OpSpec.NULL
    return typecheck_opspec(vm, w_opspec, [wam_l, wam_r],
                           dispatch="multi",
                           errmsg="cannot do `{0}` < `{1}`")

@OP.builtin_func(color="blue")
def w_LE(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_ltype = wam_l.w_static_T
    if w_opspec := MM.get_binary_opspec("<=", wam_l, wam_r):
        pass
    elif w_le := w_ltype.lookup_func("__le__"):
        w_opspec = vm.fast_metacall(w_le, [wam_l, wam_r])
    else:
        w_opspec = W_OpSpec.NULL
    return typecheck_opspec(vm, w_opspec, [wam_l, wam_r],
                           dispatch="multi",
                           errmsg="cannot do `{0}` <= `{1}`")

@OP.builtin_func(color="blue")
def w_GT(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_ltype = wam_l.w_static_T
    if w_opspec := MM.get_binary_opspec(">", wam_l, wam_r):
        pass
    elif w_gt := w_ltype.lookup_func("__gt__"):
        w_opspec = vm.fast_metacall(w_gt, [wam_l, wam_r])
    else:
        w_opspec = W_OpSpec.NULL
    return typecheck_opspec(vm, w_opspec, [wam_l, wam_r],
                           dispatch="multi",
                           errmsg="cannot do `{0}` > `{1}`")

@OP.builtin_func(color="blue")
def w_GE(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_ltype = wam_l.w_static_T
    if w_opspec := MM.get_binary_opspec(">=", wam_l, wam_r):
        pass
    elif w_ge := w_ltype.lookup_func("__ge__"):
        w_opspec = vm.fast_metacall(w_ge, [wam_l, wam_r])
    else:
        w_opspec = W_OpSpec.NULL
    return typecheck_opspec(vm, w_opspec, [wam_l, wam_r],
                           dispatch="multi",
                           errmsg="cannot do `{0}` >= `{1}`")
