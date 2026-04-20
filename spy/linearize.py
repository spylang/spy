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
from spy.util import magic_dispatch
from spy.vm.function import W_ASTFunc

if TYPE_CHECKING:
    from spy.vm.object import W_Type


def linearize(w_func: W_ASTFunc) -> W_ASTFunc:
    """
    Run the linearize pass on the given already-redshifted function.
    """
    assert w_func.redshifted, "linearize must run after redshift"
    lin = Linearizer(w_func)
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

    def __init__(self, w_func: W_ASTFunc) -> None:
        self.w_func = w_func
        self.new_locals = {}
        self.tmp_counter = 0
        self.hoisted = []

    def linearize(self) -> W_ASTFunc:
        funcdef = self.w_func.funcdef
        new_body = self.visit_body(funcdef.body)
        new_funcdef = funcdef.replace(body=new_body)

        assert self.w_func.locals_types_w is not None
        new_locals_types_w = dict(self.w_func.locals_types_w)
        new_locals_types_w.update(self.new_locals)

        return W_ASTFunc(
            fqn=self.w_func.fqn,
            closure=self.w_func.closure,
            w_functype=self.w_func.w_functype,
            funcdef=new_funcdef,
            defaults_w=self.w_func.defaults_w,
            locals_types_w=new_locals_types_w,
        )

    # ==== helpers ====

    def fresh_tmp(self, w_T: "W_Type") -> str:
        """
        Allocate a fresh local name of the given type: $v0, $v1, ...
        """
        name = f"$v{self.tmp_counter}"
        self.tmp_counter += 1
        self.new_locals[name] = w_T
        return name

    def spill(self, expr: ast.Expr) -> ast.Expr:
        """
        Evaluate ``expr`` into a fresh temp, emitting the assignment in
        ``self.hoisted``, and return a Name expression referring to the temp.

        Used to preserve left-to-right evaluation order when a later operand
        has side effects (or hoists stmts).
        """
        # XXX IMPLEMENT ME
        raise NotImplementedError

    # ==== statements ====

    def visit_body(self, body: list[ast.Stmt]) -> list[ast.Stmt]:
        """
        Visit a list of statements, returning the new (linearized) list.
        """
        new_body: list[ast.Stmt] = []
        for stmt in body:
            new_body += self.visit_stmt(stmt)
        return new_body

    def visit_stmt(self, stmt: ast.Stmt) -> list[ast.Stmt]:
        """
        Visit a statement. Returns a list because a single input stmt may
        expand into multiple output stmts (due to hoisted BlockExpr bodies
        and/or spilled temps).

        Each visit_stmt_* gets a fresh empty ``self.hoisted`` and should not
        worry about prepending it: the wrapper prepends whatever was hoisted
        during expression visits, and restores the caller's list.
        """
        saved = self.hoisted
        self.hoisted = []
        new_stmts = magic_dispatch(self, "visit_stmt", stmt)
        hoisted = self.hoisted
        self.hoisted = saved
        return hoisted + new_stmts

    def visit_stmt_Pass(self, stmt: ast.Pass) -> list[ast.Stmt]:
        return [stmt]

    def visit_stmt_Break(self, stmt: ast.Break) -> list[ast.Stmt]:
        return [stmt]

    def visit_stmt_Continue(self, stmt: ast.Continue) -> list[ast.Stmt]:
        return [stmt]

    def visit_stmt_Return(self, ret: ast.Return) -> list[ast.Stmt]:
        new_value = self.visit_expr(ret.value)
        return [ret.replace(value=new_value)]

    def visit_stmt_VarDef(self, vardef: ast.VarDef) -> list[ast.Stmt]:
        if vardef.value is None:
            return [vardef]
        new_value = self.visit_expr(vardef.value)
        return [vardef.replace(value=new_value)]

    def visit_stmt_AssignLocal(self, assign: ast.AssignLocal) -> list[ast.Stmt]:
        # XXX IMPLEMENT ME
        raise NotImplementedError

    def visit_stmt_AssignCell(self, assign: ast.AssignCell) -> list[ast.Stmt]:
        # XXX IMPLEMENT ME
        raise NotImplementedError

    def visit_stmt_UnpackAssign(self, unpack: ast.UnpackAssign) -> list[ast.Stmt]:
        # XXX IMPLEMENT ME
        raise NotImplementedError

    def visit_stmt_StmtExpr(self, stmt: ast.StmtExpr) -> list[ast.Stmt]:
        # XXX IMPLEMENT ME
        raise NotImplementedError

    def visit_stmt_If(self, if_node: ast.If) -> list[ast.Stmt]:
        # XXX IMPLEMENT ME
        raise NotImplementedError

    def visit_stmt_While(self, while_node: ast.While) -> list[ast.Stmt]:
        # XXX IMPLEMENT ME: note that hoisted stmts coming from the `test`
        # expr need to be replicated both before the loop AND at the end of
        # the body, so that they are re-evaluated each iteration.
        raise NotImplementedError

    def visit_stmt_Assert(self, assert_node: ast.Assert) -> list[ast.Stmt]:
        # XXX IMPLEMENT ME
        raise NotImplementedError

    # ==== expressions ====

    def visit_expr(self, expr: ast.Expr) -> ast.Expr:
        """
        Visit an expression, appending any hoisted stmts to ``self.hoisted``,
        and returning the rewritten expression (which MUST be side-effect
        free w.r.t. the order of evaluation required by the parent, or be a
        simple name/constant).
        """
        return magic_dispatch(self, "visit_expr", expr)

    def visit_expr_Constant(self, const: ast.Constant) -> ast.Expr:
        return const

    def visit_expr_StrConst(self, const: ast.StrConst) -> ast.Expr:
        return const

    def visit_expr_FQNConst(self, const: ast.FQNConst) -> ast.Expr:
        return const

    def visit_expr_NameLocalDirect(self, name: ast.NameLocalDirect) -> ast.Expr:
        return name

    def visit_expr_NameOuterCell(self, name: ast.NameOuterCell) -> ast.Expr:
        return name

    def visit_expr_BlockExpr(self, block: ast.BlockExpr) -> ast.Expr:
        """
        Flatten a BlockExpr: hoist its body into the surrounding stmt list,
        then visit and return its value expression.
        """
        self.hoisted += self.visit_body(block.body)
        return self.visit_expr(block.value)

    def visit_expr_Call(self, call: ast.Call) -> ast.Expr:
        """
        Visit a Call, preserving left-to-right evaluation order for func and
        args by spilling earlier operands when later ones have hoisted stmts.
        """
        # XXX IMPLEMENT ME
        raise NotImplementedError

    def visit_expr_CallMethod(self, op: ast.CallMethod) -> ast.Expr:
        # XXX IMPLEMENT ME
        raise NotImplementedError

    def visit_expr_And(self, op: ast.And) -> ast.Expr:
        """
        Short-circuit: if the RHS produces hoisted stmts, we cannot emit them
        unconditionally. Instead, lower `a and b` into an ``if`` which writes
        the result into a fresh temp, and return a Name referencing it.
        """
        # XXX IMPLEMENT ME
        raise NotImplementedError

    def visit_expr_Or(self, op: ast.Or) -> ast.Expr:
        # XXX IMPLEMENT ME: symmetric to visit_expr_And
        raise NotImplementedError

    def visit_expr_AssignExprLocal(self, assignexpr: ast.AssignExprLocal) -> ast.Expr:
        # XXX IMPLEMENT ME
        raise NotImplementedError

    def visit_expr_AssignExprCell(self, assignexpr: ast.AssignExprCell) -> ast.Expr:
        # XXX IMPLEMENT ME
        raise NotImplementedError
