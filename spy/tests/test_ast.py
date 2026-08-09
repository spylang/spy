import pytest

from spy import ast
from spy.ast import _parse_state_spec, astnode
from spy.location import Loc


@astnode("parsed")
class FakeStmt(ast.Stmt):
    pass


@astnode(">= astcompiled")
class FakeIRStmt(ast.Stmt):
    pass


def test_parse_state_spec():
    assert _parse_state_spec("parsed") == frozenset({"parsed"})
    assert _parse_state_spec("<= astcompiled") == frozenset({"parsed", "astcompiled"})
    assert _parse_state_spec("< redshifted") == frozenset(
        {"parsed", "astcompiled", "redshifting"}
    )
    assert _parse_state_spec(">= redshifted") == frozenset({"redshifted", "linearized"})
    assert _parse_state_spec("> astcompiled") == frozenset(
        {"redshifting", "redshifted", "linearized"}
    )

    with pytest.raises(ValueError):
        _parse_state_spec("bogus")


def test_astnode_with_spec_sets_valid_states():
    assert FakeStmt._valid_states == frozenset({"parsed"})  # type: ignore[attr-defined]
    assert FakeIRStmt._valid_states == frozenset(  # type: ignore[attr-defined]
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
    outer = ast.If(
        loc=Loc.fake(), test=ast.Auto(loc=Loc.fake()), then_body=[inner], else_body=[]
    )
    with pytest.raises(Exception, match="FakeStmt.*not valid at state 'astcompiled'"):
        outer.assert_valid_at("astcompiled")
