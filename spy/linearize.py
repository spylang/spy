"""
Linearize: IR-to-IR pass which rewrites an already-redshifted AST so that
expression evaluation order is explicit at the statement level.

It runs AFTER doppler and BEFORE the C backend.

The original problem is that Python and SPy guarantee left-to-right evaluation of
expressions, while C doesn't most of the time.  Take this example:

    def foo() -> int:
        print('foo')
        return 1

    def bar() -> int:
        print('bar')
        return 2


    def fn(a: int, b: int) -> int:
        return a + b

    def main() -> None:
        fn(foo(), bar())

SPy guarantees that `foo` is called before `bar`, and thus the output is always
`foo\nbar`.

However, C doesn't guarantee order of evaluation. So a naive C translation into
`fn(foo(), bar())` might print `bar\nfoo`.

The solution is to emit something like this:

    int main(void) {
        int $v0 = foo();
        int $v1 = bar();
        fn($v0, $v1);
    }

"Linearize" does exactly that, so that the C backend has an easier time to emit the
correct C code.

The pass enforces two invariants on the output AST:

1. Flattening: ``ast.BlockExpr`` nodes are eliminated. Their ``body``
   statements are hoisted into statement position, and the ``value``
   expression takes the place of the BlockExpr in the surrounding context.

2. Sequencing: when an expression contains side-effecting subexpressions
   which may be evaluated in an order that C does not guarantee (e.g. the
   two operands of a ``+``, or the arguments of a call), the operands are
   spilled into temporaries in the correct left-to-right order.

Both transformations share the same machinery: a "hoisted statements" list
threaded through expression visitors, plus a helper which spills an expr to
a fresh temp and records the spill in that list.

Short-circuit / conditional contexts (``and``, ``or``, ternary-like
constructs) are lowered into explicit ``if`` statements whenever their
non-leading branch contains hoisted statements: we cannot spill *into* the
branch without changing evaluation semantics, so we must materialize the
branch as a proper conditional instead.
"""

from typing import TYPE_CHECKING, Optional

from spy import ast
from spy.analyze.symtable import Symbol, SymTable
from spy.location import Loc
from spy.util import magic_dispatch
from spy.vm.function import W_ASTFunc, W_Func

if TYPE_CHECKING:
    from spy.vm.object import W_Type
    from spy.vm.vm import SPyVM


def linearize(vm: "SPyVM", w_func: W_ASTFunc) -> W_ASTFunc:
    """
    Run the linearize pass on the given already-redshifted function.
    """
    assert w_func.lowering_stage == "redshift", "linearize must run after redshift"
    lin = Linearizer(vm, w_func)
    return lin.linearize()


class Linearizer:
    w_func: W_ASTFunc
    # new local variables introduced by spilling, mapped to their type
    new_locals: dict[str, "W_Type"]
    # monotonically increasing counter for fresh temp names
    tmp_counter: int
    # the currently-open "hoisted statements" list: expression visitors
    # append to this list when they need to hoist stmts out of an
    # expression (either from a BlockExpr body, or from spilling)
    hoisted: list[ast.Stmt]

    def __init__(self, vm: "SPyVM", w_func: W_ASTFunc) -> None:
        self.vm = vm
        self.w_func = w_func
        self.new_locals = {}
        self.new_symbols: list[Symbol] = []
        self.tmp_counter = 0
        self.hoisted = []

    def linearize(self) -> W_ASTFunc:
        funcdef = self.w_func.funcdef
        new_body = self.rewrite_body(funcdef.body)
        new_symtable = self._copy_symtable(funcdef.symtable)
        new_funcdef = funcdef.replace(body=new_body, symtable=new_symtable)

        assert self.w_func.locals_types_w is not None
        new_locals_types_w = dict(self.w_func.locals_types_w)
        new_locals_types_w.update(self.new_locals)

        w_newfunc = W_ASTFunc(
            fqn=self.w_func.fqn,
            closure=self.w_func.closure,
            w_functype=self.w_func.w_functype,
            funcdef=new_funcdef,
            defaults_w=self.w_func.defaults_w,
            lowering_stage="linearize",
            locals_types_w=new_locals_types_w,
        )
        # mark the original function as invalid
        self.w_func.replace_with(w_newfunc)
        return w_newfunc

    # ==== helpers ====

    def _copy_symtable(self, symtable: SymTable) -> SymTable:
        new_st = SymTable(symtable.name, symtable.color, symtable.kind)
        new_st._symbols = dict(symtable._symbols)
        new_st.implicit_imports = set(symtable.implicit_imports)
        for sym in self.new_symbols:
            new_st.add(sym)
        return new_st

    def spill(self, expr: ast.Expr) -> ast.Expr:
        assert expr.w_T is not None
        loc = expr.loc
        name, sym = self.fresh_tmp(expr.w_T, loc)
        self.hoisted.append(
            ast.AssignLocal(
                loc=loc,
                target=ast.StrConst(loc, name),
                value=expr,
            )
        )
        return ast.NameLocalDirect(loc=loc, sym=sym, w_T=expr.w_T)

    def fresh_tmp(self, w_T: "W_Type", loc: Loc) -> tuple[str, Symbol]:
        """
        Allocate a fresh local name of the given type: $v0, $v1, ...
        """
        name = f"$v{self.tmp_counter}"
        self.tmp_counter += 1
        self.new_locals[name] = w_T
        sym = Symbol(name, "var", "auto", "direct", loc=loc, type_loc=loc, level=0)
        self.new_symbols.append(sym)
        return name, sym

    def rewrite_body(self, body: list[ast.Stmt]) -> list[ast.Stmt]:
        new_body: list[ast.Stmt] = []
        for stmt in body:
            self.hoisted = []
            new_stmts = magic_dispatch(self, "rewrite_stmt", stmt)
            new_body += self.hoisted + new_stmts
        return new_body

    def rewrite_stmt_Return(self, ret: ast.Return) -> list[ast.Stmt]:
        self.to_spill = self.mark_to_spill([ret.value])
        new_value = self.rewrite_expr(ret.value)
        return [ret.replace(value=new_value)]

    def rewrite_stmt_StmtExpr(self, stmt: ast.StmtExpr) -> list[ast.Stmt]:
        self.to_spill = self.mark_to_spill([stmt.value])
        new_value = self.rewrite_expr(stmt.value)
        return [stmt.replace(value=new_value)]

    # ==== pass 1: mark ====
    #
    # Determine which expressions should be spilled to guarantee the right order of
    # evaluation.
    #
    # Expressions can be:
    #   - pure: no side effects, no dependence on mutable state; never spilled.
    #
    #   - names: trivially side-effect free, but they are not pure because earlier calls
    #     might modifiy their value. The gets added to `pending_spills`
    #
    #   - side-effecting (impure Call, or anything not whitelisted): acts
    #     as a sequence point. Promote ``pending_spills`` into ``to_spill``
    #     and mark self for spill.
    PURE_EXPRS = (ast.Constant, ast.StrConst, ast.FQNConst)

    def is_pure(self, expr: ast.Expr) -> bool:
        if isinstance(expr, self.PURE_EXPRS):
            return True
        if isinstance(expr, ast.Call) and isinstance(expr.func, ast.FQNConst):
            w_obj = self.vm.lookup_global(expr.func.fqn)
            return isinstance(w_obj, W_Func) and w_obj.is_pure()
        return False

    def mark_to_spill(self, top_exprs: list[ast.Expr]) -> set[ast.Expr]:
        """
        Walk all the given exprs and determine which sub-exprs are to spill.

        If the stmt has only ONE top-level expr (e.g. Return, StmtExpr), that expr is at
        a sequence point w.r.t. the containing stmt and is never spilled.  This is just
        a minor cosmetic optimization to avoid things like:
            v2 = ...;
            return v2;

        we can directly do:
            return ...;
        """
        to_skip = top_exprs[0] if len(top_exprs) == 1 else None
        pending_spills: set[ast.Expr] = set()
        to_spill: set[ast.Expr] = set()
        for top in top_exprs:
            # walk_postorder is the same order as normal Python/SPy evaluation
            # order. E.g. fn(1, 2, 3) we evaluate them as 1, 2, 3, fn(...)
            for node in top.walk_postorder(ast.Expr):
                assert isinstance(node, ast.Expr)
                if node is to_skip:
                    continue
                if self.is_pure(node):
                    continue
                if isinstance(node, ast.NameLocalDirect):
                    pending_spills.add(node)
                    continue
                # side-effecting: flush pending into to_spill and mark self
                to_spill |= pending_spills
                pending_spills.clear()
                to_spill.add(node)
        return to_spill

    # ==== pass 2: rewrite ====

    def rewrite_expr(self, expr: ast.Expr) -> ast.Expr:
        new_expr = magic_dispatch(self, "rewrite_expr", expr)
        if expr in self.to_spill:
            return self.spill(new_expr)
        return new_expr

    def rewrite_expr_Call(self, call: ast.Call) -> ast.Expr:
        new_func = self.rewrite_expr(call.func)
        new_args = [self.rewrite_expr(a) for a in call.args]
        return call.replace(func=new_func, args=new_args)

    def rewrite_expr_FQNConst(self, const: ast.FQNConst) -> ast.Expr:
        return const

    def rewrite_expr_NameLocalDirect(self, name: ast.NameLocalDirect) -> ast.Expr:
        return name

    def rewrite_expr_StrConst(self, const: ast.StrConst) -> ast.Expr:
        return const

    def rewrite_expr_Constant(self, const: ast.Constant) -> ast.Expr:
        return const
