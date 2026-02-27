"""
Expression sequencing pass for the C backend.

This module rewrites one typed `ast.Stmt` into an equivalent statement list
whose expression evaluation order is explicit and safe to lower to C.

Why this exists:
- C leaves operand evaluation order unspecified in many contexts.
- SPy semantics require left-to-right evaluation.
- Some expressions (`and`/`or`, assignment expressions, effectful calls) need
  statement-level rewrites to preserve those semantics.

What this pass does:
- emits pre-statements for subexpressions when ordering must be made explicit;
- materializes selected subexpressions into compiler-generated temporaries;
- lowers short-circuit expressions with RHS preludes into `if`-based control flow;
- rewrites certain `while`/`assert` cases so preludes execute with correct timing.

Assumptions and heuristics:
- input is already typed (`expr.w_T` is expected to be set);
- purity is FQN-based: known pure FQNs are treated as effect-free, while
  unknown/non-FQN call targets are treated conservatively as effectful;
- temporary insertion follows two rules:
  1) preserve ordering when an effectful part precedes later
     ordering-sensitive work;
  2) snapshot unstable reads only when later effects could change observed
     values;
- optimization: direct mutable locals that are never written later in the same
  call-part sequence are not snapshotted;
- assumption for that optimization: caller direct locals are frame-private, and
  only explicit local writes in the current expression can rebind them.
- tmp index growth relies on Python's unbounded integers; fixed-width ports
  should add an explicit overflow guard when advancing the tmp counter.

The transform is backend-local:
- it runs inside C emission right before nodes are lowered to C;
- it returns rewritten nodes/tmp metadata instead of mutating earlier phases.
"""

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
    """Rewrite expressions into explicit, ordered statement form."""

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
        """Initialize tmp naming and purity policy for one sequencing pass."""
        self.tmp_prefix = tmp_prefix
        self.next_tmp_index = start_index
        self.tmpvars = []
        self.tmp_names = set()
        self.is_pure_fqn = is_pure_fqn

    def _sequence_stmt(self, stmt: ast.Stmt) -> list[ast.Stmt]:
        """Sequence a statement and return replacement statements."""
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
        """Sequence each statement in a block and flatten the result."""
        out: list[ast.Stmt] = []
        for stmt in body:
            out.extend(self._sequence_stmt(stmt))
        return out

    def _sequence_expr(self, expr: ast.Expr) -> _ExprState:
        """Sequence an expression and collect its required pre-statements."""
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
        """Sequence call func/args left-to-right and insert tmps when needed."""
        # `states[0]` corresponds to the call target expression, and `states[1:]`
        # are the argument expressions in source order.
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
        ordering_flags = [
            self._needs_ordering(
                state=state,
                facts=expr_eval_facts[i],
                all_written_names=all_written_names,
            )
            for i, state in enumerate(states)
        ]
        # Precompute right-to-left summaries so each part can query 'all later parts'
        # with a single index lookup (i+1) instead of rescanning the suffix.
        # - any later side effects
        # - any later ordering-sensitive pieces
        # - which local names are written later
        suffix_has_effects = self._suffix_any(has_effect_flags)
        suffix_ordering = self._suffix_any(ordering_flags)
        suffix_written_names = self._suffix_union(writes_per_state)

        for i, state in enumerate(states):
            pre_stmts.extend(state.pre_stmts)
            later_written_names = suffix_written_names[i + 1]
            need_tmp_for_effects, need_tmp_for_snapshot = self._tmp_requirements(
                state=state,
                facts=expr_eval_facts[i],
                later_has_effects=suffix_has_effects[i + 1],
                later_needs_ordering=suffix_ordering[i + 1],
                later_written_names=later_written_names,
            )

            if self._can_hoist_assignexpr_local(
                expr=state.expr,
                need_tmp_for_effects=need_tmp_for_effects,
                later_written_names=later_written_names,
            ):
                # The assignment itself can be hoisted as a standalone stmt.
                # We can then pass the assigned local by name and avoid a tmp.
                assert isinstance(state.expr, ast.AssignExprLocal)
                assign, ref = self._hoist_assignexpr_local(state.expr)
                pre_stmts.append(assign)
                new_parts.append(ref)
                continue

            if need_tmp_for_effects or need_tmp_for_snapshot:
                # Materialize now to freeze ordering/value before later pieces run.
                ref, assign = self._make_tmp(state.expr)
                pre_stmts.append(assign)
                new_parts.append(ref)
            else:
                new_parts.append(state.expr)

        new_call = call.replace(func=new_parts[0], args=new_parts[1:])
        return _ExprState(new_call, pre_stmts, has_side_effects, is_stable)

    def _needs_ordering(
        self,
        *,
        state: _ExprState,
        facts: _ExprEvalFacts,
        all_written_names: set[str],
    ) -> bool:
        """Return whether this part must preserve evaluation position."""
        ordering = state.has_side_effects or (not facts.is_stable)
        if self._is_unwritten_mutable_local(
            state.expr, written_names=all_written_names
        ):
            # If this local is never written by any part of the call, we only
            # need ordering when reading it itself has side effects.
            return state.has_side_effects
        return ordering

    def _tmp_requirements(
        self,
        *,
        state: _ExprState,
        facts: _ExprEvalFacts,
        later_has_effects: bool,
        later_needs_ordering: bool,
        later_written_names: set[str],
    ) -> tuple[bool, bool]:
        """Compute tmp needs for effects ordering and value snapshotting."""
        # If evaluating this part can cause effects, we must materialize it before
        # any later part that itself requires ordered evaluation.
        need_tmp_for_effects = facts.has_side_effects and later_needs_ordering
        # If this part is a pure-but-unstable read, snapshot it only when later
        # effects might change the observed value.
        need_tmp_for_snapshot = (
            (not facts.has_side_effects) and later_has_effects and (not facts.is_stable)
        )
        if need_tmp_for_snapshot and self._is_unwritten_mutable_local(
            state.expr, written_names=later_written_names
        ):
            # Assumption: caller direct locals are frame-private and only explicit
            # local writes can rebind them. Under that model, if this local name
            # is never written later, we can skip snapshotting even when later
            # expressions are effectful.
            need_tmp_for_snapshot = False
        return need_tmp_for_effects, need_tmp_for_snapshot

    @staticmethod
    def _can_hoist_assignexpr_local(
        *,
        expr: ast.Expr,
        need_tmp_for_effects: bool,
        later_written_names: set[str],
    ) -> bool:
        """Return whether assignexpr-local can be hoisted instead of tmp."""
        return (
            need_tmp_for_effects
            and isinstance(expr, ast.AssignExprLocal)
            and expr.target.value not in later_written_names
        )

    def _hoist_assignexpr_local(
        self, expr: ast.AssignExprLocal
    ) -> tuple[ast.AssignLocal, ast.NameLocalDirect]:
        """Turn `x := value` into `x = value` plus direct local reference."""
        assign = ast.AssignLocal(
            loc=expr.loc,
            target=expr.target,
            value=expr.value,
        )
        ref = self._make_local_ref(
            name=expr.target.value,
            loc=expr.loc,
            w_T=self._expr_type(expr),
        )
        return assign, ref

    @staticmethod
    def _is_unwritten_mutable_local(expr: ast.Expr, *, written_names: set[str]) -> bool:
        """Check for mutable direct local reads never written in the scope set."""
        return (
            isinstance(expr, ast.NameLocalDirect)
            and expr.sym.varkind != "const"
            and expr.sym.name not in written_names
        )

    def _analyze_expr_eval(self, expr: ast.Expr) -> _ExprEvalFacts:
        """Summarize an expression's side-effects and value stability."""
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
        """Lower short-circuit expressions with RHS preludes into explicit ifs."""
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

        # RHS has preludes, so expression-level `and/or` is not enough. Rewrite to:
        #   carrier = left
        #   if carrier (or not carrier for `or`):
        #       <rhs preludes>
        #       carrier = rhs
        #   result = carrier
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
        """Build runtime state from expression facts and prelude statements."""
        return _ExprState(
            expr=expr,
            pre_stmts=pre_stmts,
            has_side_effects=facts.has_side_effects,
            is_stable=facts.is_stable,
        )

    @staticmethod
    def _facts_from_state(state: _ExprState) -> _ExprEvalFacts:
        """Project evaluation facts from an `_ExprState`."""
        return _ExprEvalFacts(
            has_side_effects=state.has_side_effects,
            is_stable=state.is_stable,
        )

    @staticmethod
    def _merge_eval_facts(
        left: _ExprEvalFacts, right: _ExprEvalFacts
    ) -> _ExprEvalFacts:
        """Combine eval facts for sequentially evaluated subexpressions."""
        has_side_effects = left.has_side_effects or right.has_side_effects
        return _ExprEvalFacts(
            has_side_effects=has_side_effects,
            is_stable=(not has_side_effects) and left.is_stable and right.is_stable,
        )

    @staticmethod
    def _assign_expr_facts() -> _ExprEvalFacts:
        """Facts for assignment expressions: effectful and unstable."""
        return _ExprEvalFacts(has_side_effects=True, is_stable=False)

    @staticmethod
    def _leaf_eval_facts(expr: ast.Expr) -> _ExprEvalFacts | None:
        """Return eval facts for supported leaf expressions, else `None`."""
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
        """Compute suffix OR flags, including an empty-suffix sentinel slot."""
        out = [False] * (len(flags) + 1)
        for i in range(len(flags) - 1, -1, -1):
            out[i] = flags[i] or out[i + 1]
        return out

    @staticmethod
    def _suffix_union(names: list[set[str]]) -> list[set[str]]:
        """Compute suffix unions of name sets with an empty-suffix sentinel."""
        out: list[set[str]] = [set() for _ in range(len(names) + 1)]
        for i in range(len(names) - 1, -1, -1):
            out[i] = set(out[i + 1])
            out[i].update(names[i])
        return out

    def _make_tmp(self, expr: ast.Expr) -> tuple[ast.NameLocalDirect, ast.AssignLocal]:
        """Materialize an expression into a fresh compiler-generated local tmp."""
        w_T = self._expr_type(expr)
        assert w_T is not TYPES.w_NoneType, "cannot materialize void expressions"

        # Porting note: Python ints do not overflow. If this pass is reimplemented
        # with fixed-width integers (e.g. in self-hosted SPy), guard this increment.
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
        """Return carrier local for short-circuit result, reusing existing tmps."""
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

        # Both sides are compiler tmps. Rewrite RHS preludes to write into
        # `carrier` directly and drop the redundant RHS tmp.
        renamed = [
            self._rename_local_stmt(stmt, old_name=rhs_name, new_name=carrier_name)
            for stmt in rhs.pre_stmts
        ]
        self._drop_tmp(rhs_name)
        return renamed, carrier, False

    def _drop_tmp(self, tmp_name: str) -> None:
        """Forget a tmp variable after coalescing away its final use."""
        if tmp_name not in self.tmp_names:
            return
        self.tmp_names.remove(tmp_name)
        self.tmpvars = [(name, w_T) for name, w_T in self.tmpvars if name != tmp_name]

    def _rename_local_stmt(
        self, stmt: ast.Stmt, *, old_name: str, new_name: str
    ) -> ast.Stmt:
        """Rename direct local occurrences in a sequenced statement tree."""
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
        """Rename direct local occurrences inside supported expression nodes."""
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
        """Create a synthetic direct-local reference with the provided type."""
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
        """Return expression type, requiring it to be already resolved."""
        assert expr.w_T is not None, (
            "expr_sequencer requires all expressions to have w_T set"
        )
        return expr.w_T

    def _is_pure_call(self, func_expr: ast.Expr) -> bool:
        """Return whether a call target is known pure by FQN classification."""
        if not isinstance(func_expr, ast.FQNConst):
            return False
        return self.is_pure_fqn(func_expr.fqn)

    def _written_local_names_node(self, node: ast.Node) -> set[str]:
        """Collect direct-local names written by a node subtree."""
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
        """Collect local names written by expression and its prelude stmts."""
        names = self._written_local_names_node(state.expr)
        for stmt in state.pre_stmts:
            names.update(self._written_local_names_node(stmt))
        return names


def _default_is_pure_fqn(fqn: FQN) -> bool:
    """Default purity policy: pure operator calls except `operator::raise`."""
    return fqn.modname == "operator" and fqn.symbol_name != "raise"


def expr_sequencer(
    stmt: ast.Stmt,
    *,
    start_index: int = 0,
    tmp_prefix: str = "spy_tmp",
    is_pure_fqn: IsPureFQN = _default_is_pure_fqn,
) -> tuple[list[TmpVar], list[ast.Stmt], int]:
    """Sequence one statement into ordered form and return emitted tmp metadata."""
    sequencer = _ExprSequencer(
        start_index=start_index,
        tmp_prefix=tmp_prefix,
        is_pure_fqn=is_pure_fqn,
    )
    stmts = sequencer._sequence_stmt(stmt)
    return sequencer.tmpvars, stmts, sequencer.next_tmp_index
