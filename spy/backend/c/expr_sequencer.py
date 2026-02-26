from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from spy import ast
from spy.analyze.symtable import Symbol
from spy.fqn import FQN
from spy.location import Loc
from spy.vm.b import TYPES, B

if TYPE_CHECKING:
    from spy.vm.object import W_Type

TmpVar = tuple[str, "W_Type"]
IsPureFQN = Callable[[FQN], bool]


@dataclass
class _ExprState:
    expr: ast.Expr
    pre_stmts: list[ast.Stmt]
    has_side_effects: bool
    is_stable: bool


@dataclass(frozen=True)
class _ExprEvalFacts:
    has_side_effects: bool
    is_stable: bool


class _ExprSequencer:
    tmp_prefix: str
    next_tmp_index: int
    tmpvars: list[TmpVar]
    tmp_names: set[str]
    is_pure_fqn: IsPureFQN

    def __init__(
        self,
        *,
        start_index: int,
        tmp_prefix: str,
        is_pure_fqn: IsPureFQN,
    ) -> None:
        self.tmp_prefix = tmp_prefix
        self.next_tmp_index = start_index
        self.tmpvars = []
        self.tmp_names = set()
        self.is_pure_fqn = is_pure_fqn

    def _sequence_stmt(self, stmt: ast.Stmt) -> list[ast.Stmt]:
        if isinstance(stmt, (ast.Pass, ast.Break, ast.Continue)):
            return [stmt]

        if isinstance(stmt, ast.Return):
            value = self._sequence_expr(stmt.value)
            return value.pre_stmts + [stmt.replace(value=value.expr)]

        if isinstance(stmt, ast.VarDef):
            if stmt.value is None:
                return [stmt]
            value = self._sequence_expr(stmt.value)
            return value.pre_stmts + [stmt.replace(value=value.expr)]

        if isinstance(stmt, ast.AssignLocal):
            value = self._sequence_expr(stmt.value)
            return value.pre_stmts + [stmt.replace(value=value.expr)]

        if isinstance(stmt, ast.AssignCell):
            value = self._sequence_expr(stmt.value)
            return value.pre_stmts + [stmt.replace(value=value.expr)]

        if isinstance(stmt, ast.StmtExpr):
            value = self._sequence_expr(stmt.value)
            return value.pre_stmts + [stmt.replace(value=value.expr)]

        if isinstance(stmt, ast.If):
            test = self._sequence_expr(stmt.test)
            then_body = self._sequence_body(stmt.then_body)
            else_body = self._sequence_body(stmt.else_body)
            new_if = stmt.replace(
                test=test.expr, then_body=then_body, else_body=else_body
            )
            return test.pre_stmts + [new_if]

        if isinstance(stmt, ast.While):
            test = self._sequence_expr(stmt.test)
            body = self._sequence_body(stmt.body)
            if not test.pre_stmts:
                return [stmt.replace(test=test.expr, body=body)]

            # Evaluate test preludes on every iteration, then decide whether
            # to break. This preserves both sequencing and while semantics.
            loop = ast.While(
                loc=stmt.loc,
                test=ast.Constant(loc=stmt.loc, value=True, w_T=B.w_bool),
                body=test.pre_stmts
                + [
                    ast.If(
                        loc=stmt.loc,
                        test=test.expr,
                        then_body=body,
                        else_body=[ast.Break(loc=stmt.loc)],
                    )
                ],
            )
            return [loop]

        if isinstance(stmt, ast.Assert):
            test = self._sequence_expr(stmt.test)
            if stmt.msg is None:
                return test.pre_stmts + [stmt.replace(test=test.expr)]

            # Keep message evaluation lazy: only when assertion fails.
            msg = self._sequence_expr(stmt.msg)
            if not msg.pre_stmts:
                return test.pre_stmts + [stmt.replace(test=test.expr, msg=msg.expr)]

            # If formatting the message needs preludes, evaluate them only on
            # the failing branch.
            fail_assert = ast.Assert(
                loc=stmt.loc,
                test=ast.Constant(loc=stmt.loc, value=False, w_T=B.w_bool),
                msg=msg.expr,
            )
            lazy_assert = ast.If(
                loc=stmt.loc,
                test=test.expr,
                then_body=[],
                else_body=msg.pre_stmts + [fail_assert],
            )
            return test.pre_stmts + [lazy_assert]

        return [stmt]

    def _sequence_body(self, body: list[ast.Stmt]) -> list[ast.Stmt]:
        out: list[ast.Stmt] = []
        for stmt in body:
            out.extend(self._sequence_stmt(stmt))
        return out

    def _sequence_expr(self, expr: ast.Expr) -> _ExprState:
        leaf_facts = self._leaf_eval_facts(expr)
        if leaf_facts is not None:
            return self._state_from_facts(expr=expr, pre_stmts=[], facts=leaf_facts)

        if isinstance(expr, (ast.AssignExpr, ast.AssignExprLocal, ast.AssignExprCell)):
            value = self._sequence_expr(expr.value)
            return self._state_from_facts(
                expr=expr.replace(value=value.expr),
                pre_stmts=value.pre_stmts,
                facts=self._assign_expr_facts(),
            )

        if isinstance(expr, ast.And):
            return self._sequence_short_circuit(expr, rhs_when_test_true=True)

        if isinstance(expr, ast.Or):
            return self._sequence_short_circuit(expr, rhs_when_test_true=False)

        if isinstance(expr, ast.Call):
            return self._sequence_call(expr)

        raise NotImplementedError(
            f"expr_sequencer does not support {type(expr).__name__}"
        )

    def _sequence_call(self, call: ast.Call) -> _ExprState:
        states = [self._sequence_expr(call.func)] + [
            self._sequence_expr(arg) for arg in call.args
        ]
        writes_per_state = [self._written_local_names_state(state) for state in states]
        all_written_names: set[str] = set().union(*writes_per_state)
        expr_eval_facts = [self._analyze_expr_eval(state.expr) for state in states]

        call_is_pure = self._is_pure_call(call.func)
        has_side_effects = (not call_is_pure) or any(
            state.has_side_effects for state in states
        )
        is_stable = (
            call_is_pure
            and (not has_side_effects)
            and all(state.is_stable for state in states)
        )

        pre_stmts: list[ast.Stmt] = []
        new_parts: list[ast.Expr] = []
        has_effect_flags = [state.has_side_effects for state in states]
        ordering_flags = []
        for i, state in enumerate(states):
            ordering = state.has_side_effects or (not expr_eval_facts[i].is_stable)
            if (
                isinstance(state.expr, ast.NameLocalDirect)
                and state.expr.sym.varkind != "const"
                and state.expr.sym.name not in all_written_names
            ):
                ordering = state.has_side_effects
            ordering_flags.append(ordering)
        suffix_has_effects = self._suffix_any(has_effect_flags)
        suffix_ordering = self._suffix_any(ordering_flags)
        suffix_written_names = self._suffix_union(writes_per_state)

        for i, state in enumerate(states):
            pre_stmts.extend(state.pre_stmts)
            later_has_effects = suffix_has_effects[i + 1]
            later_needs_ordering = suffix_ordering[i + 1]
            expr_has_effects = expr_eval_facts[i].has_side_effects
            expr_is_stable = expr_eval_facts[i].is_stable

            need_tmp_for_effects = expr_has_effects and later_needs_ordering
            need_tmp_for_snapshot = (
                (not expr_has_effects) and later_has_effects and (not expr_is_stable)
            )
            if (
                need_tmp_for_snapshot
                and isinstance(state.expr, ast.NameLocalDirect)
                and state.expr.sym.varkind != "const"
                and state.expr.sym.name not in suffix_written_names[i + 1]
            ):
                need_tmp_for_snapshot = False

            if (
                need_tmp_for_effects
                and isinstance(state.expr, ast.AssignExprLocal)
                and state.expr.target.value not in suffix_written_names[i + 1]
            ):
                # The assignment itself can be hoisted as a standalone stmt.
                # We can then pass the assigned local by name and avoid a tmp.
                pre_stmts.append(
                    ast.AssignLocal(
                        loc=state.expr.loc,
                        target=state.expr.target,
                        value=state.expr.value,
                    )
                )
                new_parts.append(
                    self._make_local_ref(
                        name=state.expr.target.value,
                        loc=state.expr.loc,
                        w_T=self._expr_type(state.expr),
                    )
                )
                continue

            if need_tmp_for_effects or need_tmp_for_snapshot:
                ref, assign = self._make_tmp(state.expr)
                pre_stmts.append(assign)
                new_parts.append(ref)
            else:
                new_parts.append(state.expr)

        new_call = call.replace(func=new_parts[0], args=new_parts[1:])
        return _ExprState(new_call, pre_stmts, has_side_effects, is_stable)

    def _analyze_expr_eval(self, expr: ast.Expr) -> _ExprEvalFacts:
        leaf_facts = self._leaf_eval_facts(expr)
        if leaf_facts is not None:
            return leaf_facts

        if isinstance(expr, (ast.AssignExpr, ast.AssignExprLocal, ast.AssignExprCell)):
            return self._assign_expr_facts()

        if isinstance(expr, (ast.And, ast.Or)):
            left = self._analyze_expr_eval(expr.left)
            right = self._analyze_expr_eval(expr.right)
            return self._merge_eval_facts(left, right)

        if isinstance(expr, ast.Call):
            func = self._analyze_expr_eval(expr.func)
            args = [self._analyze_expr_eval(arg) for arg in expr.args]
            call_is_pure = self._is_pure_call(expr.func)
            has_side_effects = (
                func.has_side_effects
                or any(arg.has_side_effects for arg in args)
                or (not call_is_pure)
            )
            return _ExprEvalFacts(
                has_side_effects=has_side_effects,
                is_stable=(not has_side_effects)
                and func.is_stable
                and all(arg.is_stable for arg in args),
            )

        raise NotImplementedError(
            f"expr_sequencer does not support {type(expr).__name__}"
        )

    def _sequence_short_circuit(
        self,
        expr: ast.And | ast.Or,
        *,
        rhs_when_test_true: bool,
    ) -> _ExprState:
        left = self._sequence_expr(expr.left)
        right = self._sequence_expr(expr.right)
        facts = self._merge_eval_facts(
            self._facts_from_state(left), self._facts_from_state(right)
        )
        if not right.pre_stmts:
            return self._state_from_facts(
                expr=expr.replace(left=left.expr, right=right.expr),
                pre_stmts=left.pre_stmts,
                facts=facts,
            )

        left_ref, left_assign = self._short_circuit_carrier(left.expr)
        target = ast.StrConst(loc=expr.loc, value=left_ref.sym.name)
        rhs_stmts, rhs_expr, need_join_assign = self._coalesce_short_circuit_rhs(
            carrier=left_ref, rhs=right
        )
        rhs_body = list(rhs_stmts)
        if need_join_assign:
            rhs_body.append(
                ast.AssignLocal(loc=expr.loc, target=target, value=rhs_expr)
            )
        then_body = rhs_body if rhs_when_test_true else []
        else_body = [] if rhs_when_test_true else rhs_body

        pre_stmts = list(left.pre_stmts)
        if left_assign is not None:
            pre_stmts.append(left_assign)
        pre_stmts.append(
            ast.If(
                loc=expr.loc,
                test=left_ref,
                then_body=then_body,
                else_body=else_body,
            )
        )
        return self._state_from_facts(expr=left_ref, pre_stmts=pre_stmts, facts=facts)

    @staticmethod
    def _state_from_facts(
        *, expr: ast.Expr, pre_stmts: list[ast.Stmt], facts: _ExprEvalFacts
    ) -> _ExprState:
        return _ExprState(
            expr=expr,
            pre_stmts=pre_stmts,
            has_side_effects=facts.has_side_effects,
            is_stable=facts.is_stable,
        )

    @staticmethod
    def _facts_from_state(state: _ExprState) -> _ExprEvalFacts:
        return _ExprEvalFacts(
            has_side_effects=state.has_side_effects,
            is_stable=state.is_stable,
        )

    @staticmethod
    def _merge_eval_facts(
        left: _ExprEvalFacts, right: _ExprEvalFacts
    ) -> _ExprEvalFacts:
        has_side_effects = left.has_side_effects or right.has_side_effects
        return _ExprEvalFacts(
            has_side_effects=has_side_effects,
            is_stable=(not has_side_effects) and left.is_stable and right.is_stable,
        )

    @staticmethod
    def _assign_expr_facts() -> _ExprEvalFacts:
        return _ExprEvalFacts(has_side_effects=True, is_stable=False)

    @staticmethod
    def _leaf_eval_facts(expr: ast.Expr) -> _ExprEvalFacts | None:
        if isinstance(expr, (ast.Constant, ast.StrConst, ast.FQNConst, ast.LocConst)):
            return _ExprEvalFacts(has_side_effects=False, is_stable=True)

        if isinstance(
            expr,
            (
                ast.NameLocalDirect,
                ast.NameLocalCell,
                ast.NameOuterCell,
                ast.NameOuterDirect,
                ast.NameImportRef,
            ),
        ):
            is_stable = (
                not isinstance(
                    expr, (ast.NameLocalDirect, ast.NameLocalCell, ast.NameOuterCell)
                )
                or expr.sym.varkind == "const"
            )
            return _ExprEvalFacts(has_side_effects=False, is_stable=is_stable)

        return None

    @staticmethod
    def _suffix_any(flags: list[bool]) -> list[bool]:
        out = [False] * (len(flags) + 1)
        for i in range(len(flags) - 1, -1, -1):
            out[i] = flags[i] or out[i + 1]
        return out

    @staticmethod
    def _suffix_union(names: list[set[str]]) -> list[set[str]]:
        out: list[set[str]] = [set() for _ in range(len(names) + 1)]
        for i in range(len(names) - 1, -1, -1):
            out[i] = set(out[i + 1])
            out[i].update(names[i])
        return out

    def _make_tmp(self, expr: ast.Expr) -> tuple[ast.NameLocalDirect, ast.AssignLocal]:
        w_T = self._expr_type(expr)
        assert w_T is not TYPES.w_NoneType, "cannot materialize void expressions"

        tmp_name = f"{self.tmp_prefix}{self.next_tmp_index}"
        self.next_tmp_index += 1
        self.tmpvars.append((tmp_name, w_T))
        self.tmp_names.add(tmp_name)

        target = ast.StrConst(loc=expr.loc, value=tmp_name)
        assign = ast.AssignLocal(loc=expr.loc, target=target, value=expr)
        sym = Symbol(
            name=tmp_name,
            varkind="const",
            varkind_origin="auto",
            storage="direct",
            loc=expr.loc,
            type_loc=expr.loc,
            level=0,
        )
        ref = ast.NameLocalDirect(loc=expr.loc, sym=sym, w_T=w_T)
        return ref, assign

    def _short_circuit_carrier(
        self, expr: ast.Expr
    ) -> tuple[ast.NameLocalDirect, ast.AssignLocal | None]:
        # Nested short-circuit rewrites often feed an existing compiler-generated
        # tmp into another And/Or. Reuse that tmp as carrier to avoid tmp-to-tmp
        # copies such as `spy_tmpN = spy_tmpM`.
        if isinstance(expr, ast.NameLocalDirect) and expr.sym.name in self.tmp_names:
            return expr, None
        ref, assign = self._make_tmp(expr)
        return ref, assign

    def _coalesce_short_circuit_rhs(
        self,
        *,
        carrier: ast.NameLocalDirect,
        rhs: _ExprState,
    ) -> tuple[list[ast.Stmt], ast.Expr, bool]:
        """
        Try to rewrite RHS preludes to write directly into `carrier` when RHS
        already ends in a compiler-generated tmp. This removes redundant
        tmp-to-tmp joins such as `spy_tmpN = spy_tmpM`.
        """
        if not isinstance(rhs.expr, ast.NameLocalDirect):
            return rhs.pre_stmts, rhs.expr, True

        rhs_name = rhs.expr.sym.name
        carrier_name = carrier.sym.name
        if rhs_name == carrier_name:
            return rhs.pre_stmts, rhs.expr, False
        if rhs_name not in self.tmp_names or carrier_name not in self.tmp_names:
            return rhs.pre_stmts, rhs.expr, True

        renamed = [
            self._rename_local_stmt(stmt, old_name=rhs_name, new_name=carrier_name)
            for stmt in rhs.pre_stmts
        ]
        self._drop_tmp(rhs_name)
        return renamed, carrier, False

    def _drop_tmp(self, tmp_name: str) -> None:
        if tmp_name not in self.tmp_names:
            return
        self.tmp_names.remove(tmp_name)
        self.tmpvars = [(name, w_T) for name, w_T in self.tmpvars if name != tmp_name]

    def _rename_local_stmt(
        self, stmt: ast.Stmt, *, old_name: str, new_name: str
    ) -> ast.Stmt:
        if isinstance(stmt, ast.AssignLocal):
            target = stmt.target
            if target.value == old_name:
                target = target.replace(value=new_name)
            return stmt.replace(
                target=target,
                value=self._rename_local_expr(
                    stmt.value, old_name=old_name, new_name=new_name
                ),
            )
        if isinstance(stmt, ast.If):
            return stmt.replace(
                test=self._rename_local_expr(
                    stmt.test, old_name=old_name, new_name=new_name
                ),
                then_body=[
                    self._rename_local_stmt(s, old_name=old_name, new_name=new_name)
                    for s in stmt.then_body
                ],
                else_body=[
                    self._rename_local_stmt(s, old_name=old_name, new_name=new_name)
                    for s in stmt.else_body
                ],
            )
        return stmt

    def _rename_local_expr(
        self, expr: ast.Expr, *, old_name: str, new_name: str
    ) -> ast.Expr:
        if isinstance(expr, ast.NameLocalDirect) and expr.sym.name == old_name:
            return self._make_local_ref(
                name=new_name,
                loc=expr.loc,
                w_T=self._expr_type(expr),
            )
        if isinstance(expr, (ast.AssignExpr, ast.AssignExprLocal)):
            target = expr.target
            if target.value == old_name:
                target = target.replace(value=new_name)
            return expr.replace(
                target=target,
                value=self._rename_local_expr(
                    expr.value, old_name=old_name, new_name=new_name
                ),
            )
        if isinstance(expr, ast.AssignExprCell):
            return expr.replace(
                value=self._rename_local_expr(
                    expr.value, old_name=old_name, new_name=new_name
                )
            )
        if isinstance(expr, ast.Call):
            return expr.replace(
                func=self._rename_local_expr(
                    expr.func, old_name=old_name, new_name=new_name
                ),
                args=[
                    self._rename_local_expr(arg, old_name=old_name, new_name=new_name)
                    for arg in expr.args
                ],
            )
        if isinstance(expr, (ast.And, ast.Or)):
            return expr.replace(
                left=self._rename_local_expr(
                    expr.left, old_name=old_name, new_name=new_name
                ),
                right=self._rename_local_expr(
                    expr.right, old_name=old_name, new_name=new_name
                ),
            )
        return expr

    @staticmethod
    def _make_local_ref(name: str, loc: Loc, w_T: "W_Type") -> ast.NameLocalDirect:
        sym = Symbol(
            name=name,
            varkind="var",
            varkind_origin="auto",
            storage="direct",
            loc=loc,
            type_loc=loc,
            level=0,
        )
        return ast.NameLocalDirect(loc=loc, sym=sym, w_T=w_T)

    def _expr_type(self, expr: ast.Expr) -> "W_Type":
        assert expr.w_T is not None, (
            "expr_sequencer requires all expressions to have w_T set"
        )
        return expr.w_T

    def _is_pure_call(self, func_expr: ast.Expr) -> bool:
        if not isinstance(func_expr, ast.FQNConst):
            return False
        return self.is_pure_fqn(func_expr.fqn)

    def _written_local_names_node(self, node: ast.Node) -> set[str]:
        names: set[str] = set()
        for cur in node.walk():
            if isinstance(cur, ast.AssignLocal):
                names.add(cur.target.value)
            elif isinstance(cur, ast.VarDef):
                names.add(cur.name.value)
            elif isinstance(cur, (ast.AssignExpr, ast.AssignExprLocal)):
                names.add(cur.target.value)
        return names

    def _written_local_names_state(self, state: _ExprState) -> set[str]:
        names = self._written_local_names_node(state.expr)
        for stmt in state.pre_stmts:
            names.update(self._written_local_names_node(stmt))
        return names


def _default_is_pure_fqn(fqn: FQN) -> bool:
    return fqn.modname == "operator" and fqn.symbol_name != "raise"


def expr_sequencer(
    stmt: ast.Stmt,
    *,
    start_index: int = 0,
    tmp_prefix: str = "spy_tmp",
    is_pure_fqn: IsPureFQN = _default_is_pure_fqn,
) -> tuple[list[TmpVar], list[ast.Stmt], int]:
    sequencer = _ExprSequencer(
        start_index=start_index,
        tmp_prefix=tmp_prefix,
        is_pure_fqn=is_pure_fqn,
    )
    stmts = sequencer._sequence_stmt(stmt)
    return sequencer.tmpvars, stmts, sequencer.next_tmp_index
