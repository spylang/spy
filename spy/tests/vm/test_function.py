from typing import no_type_check

import pytest

from spy import ast
from spy.fqn import FQN
from spy.location import Loc
from spy.vm.b import B
from spy.vm.function import Color, FuncKind, FuncParam, W_ASTFunc
from spy.vm.object import W_Type
from spy.vm.vm import SPyVM
from spy.vm.w import W_FuncType


def make_FuncType(
    *types_w: W_Type,
    w_restype: W_Type,
    color: Color = "red",
    kind: FuncKind = "plain",
    varargs: bool = False,
) -> W_FuncType:
    """
    Small helper to make it easier to build W_FuncType.
    """
    params = [FuncParam(w_type, "simple") for w_type in types_w]
    if varargs:
        params[-1] = FuncParam(types_w[-1], "var_positional")
    return W_FuncType.new(params, w_restype, color=color, kind=kind)


def make_w_func(fqn_s: str, *, lowering_stage: str = "source") -> W_ASTFunc:
    loc = Loc.fake()
    w_functype = make_FuncType(B.w_i32, w_restype=B.w_i32)
    fqn = FQN(fqn_s)
    funcdef = ast.FuncDef(
        loc=loc,
        color="red",
        kind="plain",
        name=fqn.symbol_name,
        args=[
            ast.FuncArg(
                loc=loc, name="x", type=ast.Constant(loc=loc, value=0), kind="simple"
            )
        ],
        return_type=ast.Constant(loc=loc, value=0),
        defaults=[],
        docstring=None,
        body=[],
        decorators=[],
    )
    return W_ASTFunc(
        w_functype=w_functype,
        fqn=fqn,
        funcdef=funcdef,
        closure=(),
        defaults_w=[],
        lowering_stage=lowering_stage,
    )


class TestFunction:
    def test_FunctionType_repr(self):
        w_functype = make_FuncType(B.w_i32, B.w_i32, w_restype=B.w_bool)
        assert str(w_functype.fqn) == "builtins::def[i32, i32, bool]"
        assert repr(w_functype) == "<spy type 'def(i32, i32) -> bool'>"

    def test_FunctionType_parse(self):
        w_ft = W_FuncType.parse("def() -> i32")
        assert w_ft == make_FuncType(w_restype=B.w_i32)
        #
        w_ft = W_FuncType.parse("def(str) -> i32")
        assert w_ft == make_FuncType(B.w_str, w_restype=B.w_i32)
        #
        w_ft = W_FuncType.parse("def(str, i32,) -> i32")
        assert w_ft == make_FuncType(B.w_str, B.w_i32, w_restype=B.w_i32)

    def test_FunctionType_cache(self):
        vm = SPyVM()
        w_ft1 = W_FuncType.parse("def() -> i32")
        w_ft2 = W_FuncType.parse("def() -> i32")
        assert w_ft1 is w_ft2
        assert w_ft1 == w_ft2
        assert hash(w_ft1) == hash(w_ft2)

    def test_FunctionType_fqn(self):
        def make(color: Color, kind: FuncKind):
            return make_FuncType(
                B.w_i32, B.w_i32, w_restype=B.w_str, color=color, kind=kind
            )

        w_t1 = make("red", "plain")
        assert w_t1.fqn == FQN("builtins::def[i32, i32, str]")
        assert w_t1.fqn.human_name == "def(i32, i32) -> str"

        w_t2 = make("blue", "plain")
        assert w_t2.fqn == FQN("builtins::blue.def[i32, i32, str]")
        assert w_t2.fqn.human_name == "@blue def(i32, i32) -> str"

        w_t3 = make("blue", "generic")
        assert w_t3.fqn == FQN("builtins::blue.generic.def[i32, i32, str]")
        assert w_t3.fqn.human_name == "@blue.generic def(i32, i32) -> str"

        w_t4 = make("blue", "metafunc")
        assert w_t4.fqn == FQN("builtins::blue.metafunc.def[i32, i32, str]")
        assert w_t4.fqn.human_name == "@blue.metafunc def(i32, i32) -> str"

        w_t5 = make_FuncType(
            B.w_i32, B.w_f64, varargs=True, w_restype=B.w_str, color="red", kind="plain"
        )
        assert w_t5.fqn == FQN("builtins::def[i32, builtins::__varargs__[f64], str]")
        assert w_t5.fqn.human_name == "def(i32, *f64) -> str"

    def test_W_ASTFunc_replace_with(self):
        w_f1 = make_w_func("test::foo")
        assert w_f1.is_valid
        w_f2 = make_w_func("test::foo", lowering_stage="redshift")
        w_f1.replace_with(w_f2)
        assert not w_f1.is_valid
        assert w_f1.w_replaced_by is w_f2

    def test_W_ASTFunc_replace_with_wrong_fqn(self):
        w_f1 = make_w_func("test::foo")
        w_f2 = make_w_func("test::bar")
        with pytest.raises(AssertionError):
            w_f1.replace_with(w_f2)

    def test_W_ASTFunc_repr(self):
        w_f1 = make_w_func("test::foo")
        assert repr(w_f1) == "<spy function 'test::foo'>"
        #
        w_f2 = make_w_func("test::foo", lowering_stage="redshift")
        w_f1.replace_with(w_f2)
        assert repr(w_f1) == "<spy function 'test::foo' (invalid)>"
        assert repr(w_f2) == "<spy function 'test::foo' (redshift)>"
        #
        w_f3 = make_w_func("test::foo", lowering_stage="linearize")
        w_f2.replace_with(w_f3)
        assert repr(w_f2) == "<spy function 'test::foo' (redshift, invalid)>"
