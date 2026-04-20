from typing import TYPE_CHECKING, cast

import pytest

from spy import ast
from spy.analyze.symtable import ImportRef, Symbol, VarKind, VarStorage
from spy.backend.c.expr_sequencer import expr_sequencer
from spy.fqn import FQN
from spy.location import Loc

LOC = Loc.fake()

if TYPE_CHECKING:
    from spy.vm.object import W_Type


def _fake_w_type() -> "W_Type":
    return cast("W_Type", object())


W_I32 = _fake_w_type()
W_BOOL = _fake_w_type()
W_STR = _fake_w_type()
W_LOC = _fake_w_type()


def mk_sym(
    name: str,
    *,
    varkind: VarKind = "var",
    storage: VarStorage = "direct",
    level: int = 0,
    impref: ImportRef | None = None,
) -> Symbol:
    return Symbol(
        name=name,
        varkind=varkind,
        varkind_origin="auto",
        storage=storage,
        loc=LOC,
        type_loc=LOC,
        level=level,
        impref=impref,
    )


def i32(value: int) -> ast.Constant:
    return ast.Constant(loc=LOC, value=value, w_T=W_I32)


def bconst(value: bool) -> ast.Constant:
    return ast.Constant(loc=LOC, value=value, w_T=W_BOOL)


def name_local(
    name: str,
    *,
    varkind: VarKind = "var",
    storage: VarStorage = "direct",
    w_T: "W_Type" = W_I32,
) -> ast.NameLocalDirect:
    assert storage == "direct", "name_local helper only supports direct locals"
    return ast.NameLocalDirect(loc=LOC, sym=mk_sym(name, varkind=varkind), w_T=w_T)


def assignexpr_local(name: str, value: ast.Expr) -> ast.AssignExprLocal:
    return ast.AssignExprLocal(
        loc=LOC,
        target=ast.StrConst(loc=LOC, value=name),
        value=value,
        w_T=value.w_T,
    )


def call_fqn(fullname: str, args: list[ast.Expr], *, w_T: "W_Type") -> ast.Call:
    return ast.Call(
        loc=LOC,
        func=ast.FQNConst(loc=LOC, fqn=FQN(fullname), w_T=w_T),
        args=args,
        w_T=w_T,
    )


def sequence_stmt(
    stmt: ast.Stmt,
    *,
    start_index: int = 0,
    pure_fqns: set[tuple[str, str]] | None = None,
):
    extra_pure = pure_fqns or set()

    def is_pure_fqn(fqn: FQN) -> bool:
        return (fqn.modname == "operator" and fqn.symbol_name != "raise") or (
            fqn.modname,
            fqn.symbol_name,
        ) in extra_pure

    return expr_sequencer(stmt, start_index=start_index, is_pure_fqn=is_pure_fqn)


def add_with_assign(value: int = 1) -> ast.Call:
    return call_fqn(
        "test::add",
        [name_local("x"), assignexpr_local("x", i32(value))],
        w_T=W_I32,
    )


def pred_with_assign(value: int) -> ast.Call:
    return call_fqn(
        "test::pred",
        [name_local("x"), assignexpr_local("x", i32(value))],
        w_T=W_BOOL,
    )


class TestExprSequencer:
    @staticmethod
    def assert_no_tmp_to_tmp_forwarders(stmts: list[ast.Stmt]) -> None:
        for root in stmts:
            for node in root.walk():
                if isinstance(node, ast.AssignLocal) and isinstance(
                    node.value, ast.NameLocalDirect
                ):
                    assert not (
                        node.target.value.startswith("spy_tmp")
                        and node.value.sym.name.startswith("spy_tmp")
                    )

    @pytest.mark.parametrize(
        "stmt",
        [
            ast.Pass(loc=LOC),
            ast.Break(loc=LOC),
            ast.Continue(loc=LOC),
            ast.VarDef(
                loc=LOC,
                kind="var",
                name=ast.StrConst(loc=LOC, value="x"),
                type=ast.FQNConst(loc=LOC, fqn=FQN("builtins::i32")),
                value=None,
            ),
            ast.Raise(
                loc=LOC,
                exc=ast.FQNConst(loc=LOC, fqn=FQN("builtins::ValueError")),
            ),
        ],
        ids=["pass", "break", "continue", "vardef_none", "default_passthrough_raise"],
    )
    def test_passthrough_stmt_cases(self, stmt: ast.Stmt):
        # Snippet: statement kinds that expr_sequencer should pass through unchanged.
        tmpvars, new_stmts, next_idx = expr_sequencer(stmt)
        assert tmpvars == []
        assert next_idx == 0
        assert len(new_stmts) == 1
        assert new_stmts[0] is stmt

    @pytest.mark.parametrize(
        "expr",
        [
            ast.Constant(loc=LOC, value=1, w_T=W_I32),
            ast.StrConst(loc=LOC, value="s", w_T=W_STR),
            ast.FQNConst(loc=LOC, fqn=FQN("operator::i32_add"), w_T=W_I32),
            ast.LocConst(loc=LOC, value=LOC, w_T=W_LOC),
            ast.NameLocalDirect(loc=LOC, sym=mk_sym("x", varkind="var"), w_T=W_I32),
            ast.NameLocalCell(
                loc=LOC,
                sym=mk_sym("x_cell", varkind="const", storage="cell"),
                w_T=W_I32,
            ),
            ast.NameOuterCell(
                loc=LOC,
                sym=mk_sym("outer", varkind="var", storage="cell", level=1),
                fqn=FQN("test::outer"),
                w_T=W_I32,
            ),
            ast.NameOuterDirect(
                loc=LOC, sym=mk_sym("outer2", varkind="const", level=1), w_T=W_I32
            ),
            ast.NameImportRef(
                loc=LOC,
                sym=mk_sym(
                    "print_i32",
                    varkind="const",
                    level=1,
                    impref=ImportRef("builtins", "print_i32"),
                ),
                w_T=W_I32,
            ),
        ],
        ids=[
            "const",
            "strconst",
            "fqnconst",
            "locconst",
            "name_local_direct",
            "name_local_cell",
            "name_outer_cell",
            "name_outer_direct",
            "name_import_ref",
        ],
    )
    def test_leaf_exprs_stay_inline(self, expr: ast.Expr):
        # Snippet: return of a leaf expression (constant/name/fqn/import ref, etc.).
        stmt = ast.Return(loc=LOC, value=expr)
        tmpvars, new_stmts, next_idx = expr_sequencer(stmt)
        assert tmpvars == []
        assert next_idx == 0
        assert len(new_stmts) == 1
        assert isinstance(new_stmts[0], ast.Return)
        assert new_stmts[0].value is expr

    @pytest.mark.parametrize(
        "stmt_kind",
        ["vardef", "assign_local", "assign_cell", "stmt_expr"],
        ids=["vardef", "assign_local", "assign_cell", "stmt_expr"],
    )
    def test_stmt_kinds_sequence_value_expr(self, stmt_kind: str):
        # Snippet: each statement form wraps the same order-sensitive call `add(x, x := 1)`.
        stmt: ast.Stmt
        if stmt_kind == "vardef":
            stmt = ast.VarDef(
                loc=LOC,
                kind="var",
                name=ast.StrConst(loc=LOC, value="y"),
                type=ast.FQNConst(loc=LOC, fqn=FQN("builtins::i32")),
                value=add_with_assign(),
            )
        elif stmt_kind == "assign_local":
            stmt = ast.AssignLocal(
                loc=LOC,
                target=ast.StrConst(loc=LOC, value="y"),
                value=add_with_assign(),
            )
        elif stmt_kind == "assign_cell":
            stmt = ast.AssignCell(
                loc=LOC,
                target=ast.StrConst(loc=LOC, value="cell"),
                target_fqn=FQN("test::cell"),
                value=add_with_assign(),
            )
        else:
            stmt = ast.StmtExpr(loc=LOC, value=add_with_assign())

        tmpvars, new_stmts, next_idx = sequence_stmt(
            stmt,
            pure_fqns={("test", "add")},
        )

        assert len(tmpvars) == 1
        tmp_name, _ = tmpvars[0]
        assert next_idx == 1
        assert len(new_stmts) == 2
        assert isinstance(new_stmts[0], ast.AssignLocal)
        assert new_stmts[0].target.value == tmp_name

        seq_stmt = new_stmts[1]
        if isinstance(seq_stmt, ast.VarDef):
            value = seq_stmt.value
        elif isinstance(seq_stmt, ast.AssignLocal):
            value = seq_stmt.value
        elif isinstance(seq_stmt, ast.AssignCell):
            value = seq_stmt.value
        else:
            assert isinstance(seq_stmt, ast.StmtExpr)
            value = seq_stmt.value
        assert isinstance(value, ast.Call)
        assert isinstance(value.args[0], ast.NameLocalDirect)
        assert value.args[0].sym.name == tmp_name

    def test_if_sequences_test_and_bodies(self):
        # Snippet: `if add(x, x := 1): y = add(...); else: add(...)` sequences test and both bodies.
        stmt = ast.If(
            loc=LOC,
            test=add_with_assign(),
            then_body=[
                ast.AssignLocal(
                    loc=LOC,
                    target=ast.StrConst(loc=LOC, value="y"),
                    value=add_with_assign(),
                )
            ],
            else_body=[ast.StmtExpr(loc=LOC, value=add_with_assign())],
        )

        tmpvars, new_stmts, _ = sequence_stmt(stmt, pure_fqns={("test", "add")})

        assert len(tmpvars) == 3
        assert len(new_stmts) == 2
        assert isinstance(new_stmts[0], ast.AssignLocal)
        assert isinstance(new_stmts[1], ast.If)

        new_if = new_stmts[1]
        assert any(isinstance(s, ast.AssignLocal) for s in new_if.then_body)
        assert any(isinstance(s, ast.AssignLocal) for s in new_if.else_body)
        assert any(isinstance(s, ast.StmtExpr) for s in new_if.else_body)

    def test_while_without_test_preludes_keeps_structure(self):
        # Snippet: `while cond:` with a plain test should remain a normal while.
        stmt = ast.While(
            loc=LOC,
            test=name_local("cond", w_T=W_BOOL),
            body=[
                ast.AssignLocal(
                    loc=LOC,
                    target=ast.StrConst(loc=LOC, value="x"),
                    value=i32(0),
                )
            ],
        )

        tmpvars, new_stmts, next_idx = sequence_stmt(stmt)

        assert tmpvars == []
        assert next_idx == 0
        assert len(new_stmts) == 1
        assert isinstance(new_stmts[0], ast.While)
        assert not (
            isinstance(new_stmts[0].test, ast.Constant)
            and new_stmts[0].test.value is True
        )

    def test_while_with_test_preludes_rewrites_to_loop_with_break(self):
        # Snippet under test:
        #   while add(x, x := 1):
        #       return x
        # Expected shape:
        #   while True:
        #       <prelude for add(...)>
        #       if <sequenced test>:
        #           return x
        #       else:
        #           break
        stmt = ast.While(
            loc=LOC,
            test=add_with_assign(),
            body=[ast.Return(loc=LOC, value=name_local("x"))],
        )

        _, new_stmts, _ = sequence_stmt(stmt, pure_fqns={("test", "add")})

        assert len(new_stmts) == 1
        assert isinstance(new_stmts[0], ast.While)
        new_loop = new_stmts[0]
        assert isinstance(new_loop.test, ast.Constant)
        assert new_loop.test.value is True
        assert isinstance(new_loop.body[-1], ast.If)
        branch = new_loop.body[-1]
        assert isinstance(branch.else_body[-1], ast.Break)

    def test_assert_without_msg_sequences_only_test(self):
        # Snippet: `assert add(x, x := 1)` should sequence only the test expression.
        stmt = ast.Assert(loc=LOC, test=add_with_assign(), msg=None)

        tmpvars, new_stmts, _ = sequence_stmt(stmt, pure_fqns={("test", "add")})

        assert len(tmpvars) == 1
        assert len(new_stmts) == 2
        assert isinstance(new_stmts[0], ast.AssignLocal)
        assert isinstance(new_stmts[1], ast.Assert)
        seq_assert = new_stmts[1]
        assert seq_assert.msg is None

    def test_assert_message_preludes_remain_lazy(self):
        # Snippet under test:
        #   assert True, fmt(x, x := 1)
        # `fmt(...)` has a prelude (`x := 1`) so the rewrite must keep it lazy:
        # it should appear only in the `else` branch of an `if test` guard.
        stmt = ast.Assert(
            loc=LOC,
            test=bconst(True),
            msg=call_fqn(
                "test::fmt",
                [name_local("x"), assignexpr_local("x", i32(1))],
                w_T=W_STR,
            ),
        )

        _, new_stmts, _ = sequence_stmt(stmt, pure_fqns={("test", "fmt")})

        assert len(new_stmts) == 1
        assert isinstance(new_stmts[0], ast.If)
        lazy_if = new_stmts[0]
        assert lazy_if.then_body == []
        assert lazy_if.else_body
        assert isinstance(lazy_if.else_body[-1], ast.Assert)
        fail_assert = lazy_if.else_body[-1]
        assert isinstance(fail_assert.test, ast.Constant)
        assert fail_assert.test.value is False
        assert fail_assert.msg is not None

    @pytest.mark.parametrize(
        ("bool_expr", "branch_with_assignment"),
        [
            (
                ast.And(
                    loc=LOC,
                    left=bconst(True),
                    right=pred_with_assign(1),
                    w_T=W_BOOL,
                ),
                "then_body",
            ),
            (
                ast.Or(
                    loc=LOC,
                    left=bconst(False),
                    right=pred_with_assign(1),
                    w_T=W_BOOL,
                ),
                "else_body",
            ),
        ],
        ids=["and_with_rhs_preludes", "or_with_rhs_preludes"],
    )
    def test_short_circuit_rewrite_with_rhs_preludes(
        self, bool_expr: ast.Expr, branch_with_assignment: str
    ):
        # Snippet under test (parametrized):
        #   return True and pred(x, x := 1)
        #   return False or pred(x, x := 1)
        # RHS has preludes, so short-circuit must rewrite to:
        #   tmp = left
        #   if <short-circuit condition>:
        #       <RHS preludes>
        #       tmp = <rhs value>
        #   return tmp
        stmt = ast.Return(loc=LOC, value=bool_expr)
        _, new_stmts, _ = sequence_stmt(stmt, pure_fqns={("test", "pred")})

        assert isinstance(new_stmts[-1], ast.Return)
        ret = new_stmts[-1]
        assert isinstance(ret.value, ast.NameLocalDirect)
        if_stmt = next(s for s in new_stmts if isinstance(s, ast.If))
        branch = getattr(if_stmt, branch_with_assignment)
        assignments = [s for s in branch if isinstance(s, ast.AssignLocal)]
        assert assignments
        assert any(assign.target.value == ret.value.sym.name for assign in assignments)

    def test_nested_short_circuit_reuses_existing_carrier_tmps(self):
        # Snippet under test:
        #   b = ((True and pred(x, x := 1)) and (pred(x, x := 2) or (True and pred(x, x := 3)))) \
        #       or (False and pred(x, x := 4))
        # This stresses nested short-circuit rewrites. We validate that rewrites
        # avoid redundant forwarding like `spy_tmpN = spy_tmpM`.
        expr = ast.Or(
            loc=LOC,
            left=ast.And(
                loc=LOC,
                left=ast.And(
                    loc=LOC,
                    left=bconst(True),
                    right=pred_with_assign(1),
                    w_T=W_BOOL,
                ),
                right=ast.Or(
                    loc=LOC,
                    left=pred_with_assign(2),
                    right=ast.And(
                        loc=LOC,
                        left=bconst(True),
                        right=pred_with_assign(3),
                        w_T=W_BOOL,
                    ),
                    w_T=W_BOOL,
                ),
                w_T=W_BOOL,
            ),
            right=ast.And(
                loc=LOC,
                left=bconst(False),
                right=pred_with_assign(4),
                w_T=W_BOOL,
            ),
            w_T=W_BOOL,
        )
        stmt = ast.AssignLocal(
            loc=LOC,
            target=ast.StrConst(loc=LOC, value="b"),
            value=expr,
        )

        tmpvars, new_stmts, _ = sequence_stmt(stmt, pure_fqns={("test", "pred")})

        assert len(tmpvars) >= 4
        self.assert_no_tmp_to_tmp_forwarders(new_stmts)

    def test_assignexpr_local_is_hoisted_without_tmp(self):
        # Snippet under test:
        #   return pack(x := bump_a(), y := bump_b())
        # First argument has effects and must be sequenced before later args.
        # For local targets, sequencer should hoist to a direct assignment:
        #   x = bump_a()
        #   return pack(x, y := bump_b())
        stmt = ast.Return(
            loc=LOC,
            value=call_fqn(
                "test::pack",
                [
                    assignexpr_local(
                        "x",
                        call_fqn("test::bump_a", [], w_T=W_I32),
                    ),
                    assignexpr_local(
                        "y",
                        call_fqn("test::bump_b", [], w_T=W_I32),
                    ),
                ],
                w_T=W_I32,
            ),
        )

        tmpvars, new_stmts, _ = sequence_stmt(stmt)

        assert tmpvars == []
        assert len(new_stmts) == 2
        assert isinstance(new_stmts[0], ast.AssignLocal)
        assert isinstance(new_stmts[1], ast.Return)
        ret = new_stmts[1]
        assert isinstance(ret, ast.Return)
        assert isinstance(ret.value, ast.Call)
        assert isinstance(ret.value.args[0], ast.NameLocalDirect)
        assert ret.value.args[0].sym.name == "x"
        assert isinstance(ret.value.args[1], ast.AssignExprLocal)
        assert ret.value.args[1].target.value == "y"

    def test_assignexpr_cell_is_materialized_when_later_arg_needs_ordering(self):
        # Snippet under test:
        #   return op(x_cell := 1, x_cell := 2)
        # Cell assignment cannot be hoisted like a local assignexpr, so when
        # ordering is required the first arg should be materialized into a tmp.
        call = ast.Call(
            loc=LOC,
            func=ast.FQNConst(loc=LOC, fqn=FQN("operator::i32_add"), w_T=W_I32),
            args=[
                ast.AssignExprCell(
                    loc=LOC,
                    target=ast.StrConst(loc=LOC, value="x"),
                    target_fqn=FQN("test::x"),
                    value=ast.Constant(loc=LOC, value=1, w_T=W_I32),
                    w_T=W_I32,
                ),
                ast.AssignExprCell(
                    loc=LOC,
                    target=ast.StrConst(loc=LOC, value="x"),
                    target_fqn=FQN("test::x"),
                    value=ast.Constant(loc=LOC, value=2, w_T=W_I32),
                    w_T=W_I32,
                ),
            ],
            w_T=W_I32,
        )
        stmt = ast.Return(loc=LOC, value=call)
        tmpvars, new_stmts, _ = expr_sequencer(stmt)

        assert len(tmpvars) == 1
        assert len(new_stmts) == 2
        assert isinstance(new_stmts[0], ast.AssignLocal)
        assert isinstance(new_stmts[1], ast.Return)

        first = new_stmts[0]
        assert isinstance(first, ast.AssignLocal)
        assert isinstance(first.value, ast.AssignExprCell)
        tmp_name = first.target.value

        ret = new_stmts[1]
        assert isinstance(ret, ast.Return)
        assert isinstance(ret.value, ast.Call)
        assert isinstance(ret.value.args[0], ast.NameLocalDirect)
        assert ret.value.args[0].sym.name == tmp_name
        assert isinstance(ret.value.args[1], ast.AssignExprCell)

    def test_skips_snapshot_for_unwritten_local_with_later_effects(self):
        # Snippet under test:
        #   return add(x, bump())
        # Even though `bump()` is effectful, `x` is an unwritten mutable local in
        # this call, so snapshotting `x` into a tmp would be unnecessary.
        stmt = ast.Return(
            loc=LOC,
            value=call_fqn(
                "test::add",
                [
                    name_local("x"),
                    call_fqn("test::bump", [], w_T=W_I32),
                ],
                w_T=W_I32,
            ),
        )

        tmpvars, new_stmts, next_idx = sequence_stmt(
            stmt,
            pure_fqns={("test", "add")},
        )

        assert tmpvars == []
        assert next_idx == 0
        assert len(new_stmts) == 1
        assert isinstance(new_stmts[0], ast.Return)
        assert isinstance(new_stmts[0].value, ast.Call)
        assert isinstance(new_stmts[0].value.args[0], ast.NameLocalDirect)
        assert new_stmts[0].value.args[0].sym.name == "x"

    def test_materializes_side_effect_arg_when_followed_by_order_sensitive_arg(self):
        # Snippet under test:
        #   return add(bump(), x := 1)
        # First arg has effects and later arg is order-sensitive, so sequencer
        # should materialize first arg into a tmp to preserve left-to-right eval.
        stmt = ast.Return(
            loc=LOC,
            value=call_fqn(
                "test::add",
                [
                    call_fqn("test::bump", [], w_T=W_I32),
                    assignexpr_local("x", i32(1)),
                ],
                w_T=W_I32,
            ),
        )

        tmpvars, new_stmts, _ = sequence_stmt(
            stmt,
            pure_fqns={("test", "add")},
        )

        assert len(tmpvars) == 1
        assert len(new_stmts) == 2
        assert isinstance(new_stmts[0], ast.AssignLocal)
        assert isinstance(new_stmts[1], ast.Return)
        first = new_stmts[0]
        assert isinstance(first, ast.AssignLocal)
        assert isinstance(first.value, ast.Call)
        tmp_name = first.target.value
        ret = new_stmts[1]
        assert isinstance(ret, ast.Return)
        assert isinstance(ret.value, ast.Call)
        assert isinstance(ret.value.args[0], ast.NameLocalDirect)
        assert ret.value.args[0].sym.name == tmp_name

    def test_start_index_is_respected_for_tmp_names(self):
        # Snippet: `start_index=7` should produce first tmp named `spy_tmp7`.
        stmt = ast.Return(loc=LOC, value=add_with_assign())
        tmpvars, _, next_idx = sequence_stmt(
            stmt,
            start_index=7,
            pure_fqns={("test", "add")},
        )

        assert [name for name, _ in tmpvars] == ["spy_tmp7"]
        assert next_idx == 8

    def test_non_fqn_call_stays_inline_without_ordering_pressure(self):
        # Snippet: `return fn(1)` uses a non-FQN callee, but with no later ordering pressure.
        call = ast.Call(
            loc=LOC,
            func=ast.NameLocalDirect(loc=LOC, sym=mk_sym("fn"), w_T=W_I32),
            args=[ast.Constant(loc=LOC, value=1, w_T=W_I32)],
            w_T=W_I32,
        )
        stmt = ast.Return(loc=LOC, value=call)
        tmpvars, new_stmts, next_idx = expr_sequencer(stmt)

        assert tmpvars == []
        assert next_idx == 0
        assert len(new_stmts) == 1
        assert isinstance(new_stmts[0], ast.Return)
        assert isinstance(new_stmts[0].value, ast.Call)
        assert isinstance(new_stmts[0].value.func, ast.NameLocalDirect)
