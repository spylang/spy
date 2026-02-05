from dataclasses import dataclass

from spy.errors import SPyError
from spy.fqn import FQN
from spy.textbuilder import TextBuilder
from spy.vm.b import TYPES, B
from spy.vm.function import W_ASTFunc, W_Func
from spy.vm.modules.jsffi import JSFFI
from spy.vm.modules.posix import POSIX
from spy.vm.modules.rawbuffer import RB
from spy.vm.modules.unsafe.ptr import W_RefType
from spy.vm.object import W_Type
from spy.vm.vm import SPyVM


@dataclass
class C_Type:
    """
    Just a tiny wrapper around a string, but it helps to make things tidy.
    """

    name: str

    def __repr__(self) -> str:
        return f"<C type '{self.name}'>"

    def __str__(self) -> str:
        return self.name


@dataclass
class C_Ident:
    # C_KEYWORDS is initlized once with immutable property.
    C_KEYWORDS = (
        "auto",
        "break",
        "case",
        "char",
        "const",
        "continue",
        "default",
        "do",
        "double",
        "else",
        "enum",
        "extern",
        "float",
        "for",
        "goto",
        "if",
        "inline",
        "int",
        "long",
        "register",
        "restrict",
        "return",
        "short",
        "signed",
        "sizeof",
        "static",
        "struct",
        "switch",
        "typedef",
        "union",
        "unsigned",
        "void",
        "volatile",
        "while",
        "_Bool",
        "_Complex",
        "_Imaginary",
    )

    variable_name: str

    def check_c_keyword(self) -> str:
        if self.variable_name in self.C_KEYWORDS:
            return f"{self.variable_name}$"
        return self.variable_name

    def __str__(self) -> str:
        return self.check_c_keyword()


@dataclass
class C_FuncParam:
    name: C_Ident
    c_type: C_Type


@dataclass
class C_Function:
    name: str
    params: list[C_FuncParam]
    c_restype: C_Type

    def __repr__(self) -> str:
        return f"<C func '{self.name}'>"

    def decl(self) -> str:
        if self.params == []:
            s_params = "void"
        else:
            paramlist = [
                f"{p.c_type} {p.name}" for p in self.params if p.c_type.name != "void"
            ]
            s_params = ", ".join(paramlist)
        #
        return f"{self.c_restype} {self.name}({s_params})"


class Context:
    """
    Global context of the C writer.

    Keep track of things like the mapping from W_* types to C types.
    """

    vm: SPyVM
    tbh_includes: TextBuilder
    seen_modules: set[str]
    _d: dict[W_Type, C_Type]

    def __init__(self, vm: SPyVM) -> None:
        self.vm = vm
        self.seen_modules = set()
        # set by CModuleWriter.emit_header
        self.tbh_includes = None  # type: ignore
        self._d = {}
        self._d[TYPES.w_NoneType] = C_Type("void")
        self._d[B.w_i8] = C_Type("int8_t")
        self._d[B.w_u8] = C_Type("uint8_t")
        self._d[B.w_i32] = C_Type("int32_t")
        self._d[B.w_u32] = C_Type("uint32_t")
        self._d[B.w_f64] = C_Type("double")
        self._d[B.w_f32] = C_Type("float")
        self._d[B.w_bool] = C_Type("bool")
        self._d[B.w_str] = C_Type("spy_Str *")
        self._d[RB.w_RawBuffer] = C_Type("spy_RawBuffer *")
        self._d[JSFFI.w_JsRef] = C_Type("JsRef")
        self._d[POSIX.w_TerminalSize] = C_Type("spy_TerminalSize")

    def w2c(self, w_T: W_Type) -> C_Type:
        if w_T in self._d:
            return self._d[w_T]

        elif isinstance(w_T, W_Type):
            # as soon as we split spy_structdefs into multiple files, here we
            # should add a self.add_include_maybe. But for now it's not needed
            # because we always include spy_structdefs.h anyway.
            c_type = C_Type(w_T.fqn.c_name)
            self._d[w_T] = c_type
            return c_type

        raise NotImplementedError(f"Cannot translate type {w_T} to C")

    def c_restype_by_fqn(self, fqn: FQN) -> C_Type:
        w_func = self.vm.lookup_global(fqn)
        assert isinstance(w_func, W_Func)
        w_restype = w_func.w_functype.w_restype
        return self.w2c(w_restype)

    def c_function(self, name: str, w_func: W_ASTFunc) -> C_Function:
        w_functype = w_func.w_functype
        funcdef = w_func.funcdef

        c_params = []
        for i, param in enumerate(w_functype.params):
            c_type = self.w2c(param.w_T)
            if param.kind == "simple":
                c_param_name = C_Ident(funcdef.args[i].name)
                c_params.append(C_FuncParam(c_param_name, c_type))
            elif param.kind == "var_positional":
                assert i == len(funcdef.args) - 1
                raise SPyError.simple(
                    "W_WIP",
                    "*args not yet supported by the C backend",
                    "*args declared here",
                    funcdef.args[i].loc,
                )
            else:
                assert False

        c_restype = self.w2c(w_functype.w_restype)
        return C_Function(name, c_params, c_restype)

    def add_include_maybe(self, fqn: FQN) -> None:
        modname = fqn.modname
        if modname in self.seen_modules:
            # we already encountered this module, nothing to do
            return

        self.seen_modules.add(modname)
        w_mod = self.vm.modules_w[modname]
        if not w_mod.is_builtin():
            self.tbh_includes.wl(f'#include "{modname}.h"')
