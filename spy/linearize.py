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
        new_body = self.visit_body(funcdef.body)
        new_symtable = self._copy_symtable(funcdef.symtable)
        new_funcdef = funcdef.replace(body=new_body, symtable=new_symtable)

        assert self.w_func.locals_types_w is not None
        new_locals_types_w = dict(self.w_func.locals_types_w)
        new_locals_types_w.update(self.new_locals)

        return W_ASTFunc(
            fqn=self.w_func.fqn,
            closure=self.w_func.closure,
            w_functype=self.w_func.w_functype,
            funcdef=new_funcdef,
            defaults_w=self.w_func.defaults_w,
            lowering_stage="linearize",
            locals_types_w=new_locals_types_w,
        )

    # ==== helpers ====

    def _copy_symtable(self, symtable: SymTable) -> SymTable:
        new_st = SymTable(symtable.name, symtable.color, symtable.kind)
        new_st._symbols = dict(symtable._symbols)
        new_st.implicit_imports = set(symtable.implicit_imports)
        for sym in self.new_symbols:
            new_st.add(sym)
        return new_st

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
        assert expr.w_T is not None
        loc = expr.loc
        name = self.fresh_tmp(expr.w_T)
        sym = Symbol(
            name,
            "var",
            "auto",
            "direct",
            loc=loc,
            type_loc=loc,
            level=0,
        )
        self.new_symbols.append(sym)
        vardef = ast.VarDef(
            loc=loc,
            kind="var",
            name=ast.StrConst(loc, name),
            type=ast.FQNConst(loc, expr.w_T.fqn),
            value=expr,
        )
        self.hoisted.append(vardef)
        return ast.NameLocalDirect(loc=loc, sym=sym, w_T=expr.w_T)

    def _is_trivial(self, expr: ast.Expr) -> bool:
        """
        Return True if expr is side-effect free and doesn't need spilling.
        This includes constants, names, and calls to pure functions with
        trivial arguments.
        """
        if isinstance(
            expr,
            (
                ast.Constant,
                ast.StrConst,
                ast.FQNConst,
                ast.NameLocalDirect,
                ast.NameOuterCell,
                ast.LocConst,
            ),
        ):
            return True
        if isinstance(expr, ast.Call) and isinstance(expr.func, ast.FQNConst):
            w_func = self.vm.lookup_global(expr.func.fqn)
            if isinstance(w_func, W_Func) and w_func.is_pure():
                return True
        return False

    def visit_exprs_with_spilling(self, exprs: list[ast.Expr]) -> list[ast.Expr]:
        """
        Visit a list of expressions left-to-right. If 2+ are non-trivial
        (potentially side-effecting), spill all of them to temporaries to
        guarantee left-to-right evaluation in C.
        """
        visited = [self.visit_expr(e) for e in exprs]
        trivial = [self._is_trivial(v) for v in visited]
        to_spill = trivial.count(False)
        if to_spill >= 2:
            visited = [v if t else self.spill(v) for v, t in zip(visited, trivial)]
        return visited

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
        new_value = self.visit_expr(assign.value)
        return [assign.replace(value=new_value)]

    def visit_stmt_AssignCell(self, assign: ast.AssignCell) -> list[ast.Stmt]:
        new_value = self.visit_expr(assign.value)
        return [assign.replace(value=new_value)]

    def visit_stmt_UnpackAssign(self, unpack: ast.UnpackAssign) -> list[ast.Stmt]:
        new_value = self.visit_expr(unpack.value)
        return [unpack.replace(value=new_value)]

    def visit_stmt_StmtExpr(self, stmt: ast.StmtExpr) -> list[ast.Stmt]:
        new_value = self.visit_expr(stmt.value)
        return [stmt.replace(value=new_value)]

    def visit_stmt_If(self, if_node: ast.If) -> list[ast.Stmt]:
        new_test = self.visit_expr(if_node.test)
        new_then = self.visit_body(if_node.then_body)
        new_else = self.visit_body(if_node.else_body)
        return [if_node.replace(test=new_test, then_body=new_then, else_body=new_else)]

    def visit_stmt_While(self, while_node: ast.While) -> list[ast.Stmt]:
        # XXX TODO: if the test has hoisted stmts, they need to be replicated
        # both before the loop AND at the end of the body.
        new_test = self.visit_expr(while_node.test)
        new_body = self.visit_body(while_node.body)
        return [while_node.replace(test=new_test, body=new_body)]

    def visit_stmt_Assert(self, assert_node: ast.Assert) -> list[ast.Stmt]:
        new_test = self.visit_expr(assert_node.test)
        new_msg = None
        if assert_node.msg is not None:
            new_msg = self.visit_expr(assert_node.msg)
        return [assert_node.replace(test=new_test, msg=new_msg)]

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

    def visit_expr_LocConst(self, const: ast.LocConst) -> ast.Expr:
        return const

    def visit_expr_Tuple(self, tup: ast.Tuple) -> ast.Expr:
        new_items = [self.visit_expr(item) for item in tup.items]
        return tup.replace(items=new_items)

    def visit_expr_BlockExpr(self, block: ast.BlockExpr) -> ast.Expr:
        """
        Flatten a BlockExpr: hoist its body into the surrounding stmt list,
        then visit and return its value expression.
        """
        self.hoisted += self.visit_body(block.body)
        return self.visit_expr(block.value)

    def visit_expr_Call(self, call: ast.Call) -> ast.Expr:
        all_operands = [call.func] + call.args
        new_operands = self.visit_exprs_with_spilling(all_operands)
        new_func = new_operands[0]
        new_args = new_operands[1:]
        return call.replace(func=new_func, args=new_args)

    def visit_expr_CallMethod(self, op: ast.CallMethod) -> ast.Expr:
        # XXX IMPLEMENT ME
        raise NotImplementedError

    def visit_expr_And(self, op: ast.And) -> ast.Expr:
        # XXX TODO: lower into if/else when RHS has hoisted stmts
        new_left = self.visit_expr(op.left)
        new_right = self.visit_expr(op.right)
        return op.replace(left=new_left, right=new_right)

    def visit_expr_Or(self, op: ast.Or) -> ast.Expr:
        # XXX TODO: lower into if/else when RHS has hoisted stmts
        new_left = self.visit_expr(op.left)
        new_right = self.visit_expr(op.right)
        return op.replace(left=new_left, right=new_right)

    def visit_expr_AssignExprLocal(self, assignexpr: ast.AssignExprLocal) -> ast.Expr:
        new_value = self.visit_expr(assignexpr.value)
        return assignexpr.replace(value=new_value)

    def visit_expr_AssignExprCell(self, assignexpr: ast.AssignExprCell) -> ast.Expr:
        new_value = self.visit_expr(assignexpr.value)
        return assignexpr.replace(value=new_value)
