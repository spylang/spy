from typing import cast

import pytest

from spy import ast
from spy.analyze.sym import Scope
from spy.ast import _parse_stage_spec, astnode
from spy.location import Loc


@astnode("parsed")
class FakeStmt(ast.Stmt):
    pass


@astnode(">= astcompiled")
class FakeIRStmt(ast.Stmt):
    pass


def test_parse_stage_spec():
    assert _parse_stage_spec("parsed") == frozenset({"parsed"})
    assert _parse_stage_spec("<= astcompiled") == frozenset({"parsed", "astcompiled"})
    assert _parse_stage_spec("< redshifted") == frozenset(
        {"parsed", "astcompiled", "redshifting"}
    )
    assert _parse_stage_spec(">= redshifted") == frozenset({"redshifted", "linearized"})
    assert _parse_stage_spec("> astcompiled") == frozenset(
        {"redshifting", "redshifted", "linearized"}
    )

    with pytest.raises(ValueError):
        _parse_stage_spec("bogus")


def test_astnode_with_spec_sets_valid_stages():
    assert FakeStmt._valid_stages == frozenset({"parsed"})  # type: ignore[attr-defined]
    assert FakeIRStmt._valid_stages == frozenset(  # type: ignore[attr-defined]
        {"astcompiled", "redshifting", "redshifted", "linearized"}
    )


def test_assert_valid_node_class_ok():
    node = FakeStmt(loc=Loc.fake())
    node.assert_valid_at("parsed")


def test_assert_valid_node_class_fails():
    node = FakeStmt(loc=Loc.fake())
    with pytest.raises(Exception, match="FakeStmt.*not valid at state 'astcompiled'"):
        node.assert_valid_at("astcompiled")


def test_assert_valid_no_spec_is_always_valid():
    node = ast.Pass(loc=Loc.fake())
    node.assert_valid_at("parsed")
    node.assert_valid_at("linearized")


def test_assert_valid_recurses_into_children():
    inner = FakeStmt(loc=Loc.fake())
    dummy_scope = cast(Scope, object())
    outer = ast.If(
        loc=Loc.fake(),
        test=ast.Auto(loc=Loc.fake()),
        then=ast.Block(loc=Loc.fake(), body=[inner], scope=dummy_scope),
        else_=ast.Block(loc=Loc.fake(), body=[], scope=dummy_scope),
    )
    with pytest.raises(Exception, match="FakeStmt.*not valid at state 'astcompiled'"):
        outer.assert_valid_at("astcompiled")
