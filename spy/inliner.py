"""
Inlining pass for @force_inline functions.

This pass runs AFTER redshift. It walks the body of every red W_ASTFunc and
replaces each ast.Call to a @force_inline callee with the callee's return
expression, substituting parameters with the call-site arguments.

For now @force_inline functions must consist of a single `return <expr>`
statement (validated by W_ASTFunc.check_force_inline_valid).
"""

from typing import TYPE_CHECKING

from spy import ast
from spy.vm.function import W_ASTFunc

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


def inline_all(vm: "SPyVM") -> None:
    """
    Apply inlining to every redshifted W_ASTFunc in the VM.

    First validate all @force_inline functions, then rewrite callers.
    """
    for fqn, w_func in list(vm.globals_w.items()):
        if isinstance(w_func, W_ASTFunc) and w_func.is_force_inline:
            w_func.check_force_inline_valid()

    # Rewrite all redshifted functions (including @force_inline ones
    # themselves, in case they call other @force_inline functions).
    for fqn, w_func in list(vm.globals_w.items()):
        if isinstance(w_func, W_ASTFunc) and w_func.redshifted:
            new_func = inline_func(vm, w_func)
            if new_func is not w_func:
                vm.globals_w[fqn] = new_func


def inline_func(vm: "SPyVM", w_func: W_ASTFunc) -> W_ASTFunc:
    """
    Return a new W_ASTFunc with all calls to @force_inline functions inlined.
    If nothing changed, return the same object.
    """
    new_body = inline_body(vm, w_func.funcdef.body)
    if new_body is w_func.funcdef.body:
        return w_func

    new_funcdef = w_func.funcdef.replace(body=new_body)
    new_w_func = W_ASTFunc(
        w_functype=w_func.w_functype,
        fqn=w_func.fqn,
        funcdef=new_funcdef,
        closure=w_func.closure,
        defaults_w=w_func.defaults_w,
        locals_types_w=w_func.locals_types_w,
    )
    return new_w_func


def inline_body(vm: "SPyVM", body: list[ast.Stmt]) -> list[ast.Stmt]:
    """Inline calls inside a list of statements. Returns the same list if unchanged."""
    new_body = [inline_stmt(vm, stmt) for stmt in body]
    if all(new is old for new, old in zip(new_body, body)):
        return body
    return new_body


def inline_stmt(vm: "SPyVM", stmt: ast.Stmt) -> ast.Stmt:
    """Inline calls inside a single statement."""
    if isinstance(stmt, ast.Return):
        new_value = inline_expr(vm, stmt.value)
        return stmt if new_value is stmt.value else stmt.replace(value=new_value)

    if isinstance(stmt, ast.AssignLocal):
        new_value = inline_expr(vm, stmt.value)
        return stmt if new_value is stmt.value else stmt.replace(value=new_value)

    if isinstance(stmt, ast.Assign):
        new_value = inline_expr(vm, stmt.value)
        return stmt if new_value is stmt.value else stmt.replace(value=new_value)

    if isinstance(stmt, ast.StmtExpr):
        new_value = inline_expr(vm, stmt.value)
        return stmt if new_value is stmt.value else stmt.replace(value=new_value)

    if isinstance(stmt, ast.If):
        new_test = inline_expr(vm, stmt.test)
        new_then = inline_body(vm, stmt.then_body)
        new_else = inline_body(vm, stmt.else_body)
        if (
            new_test is stmt.test
            and new_then is stmt.then_body
            and new_else is stmt.else_body
        ):
            return stmt
        return stmt.replace(test=new_test, then_body=new_then, else_body=new_else)

    if isinstance(stmt, ast.While):
        new_test = inline_expr(vm, stmt.test)
        new_body = inline_body(vm, stmt.body)
        if new_test is stmt.test and new_body is stmt.body:
            return stmt
        return stmt.replace(test=new_test, body=new_body)

    if isinstance(stmt, ast.VarDef):
        if stmt.value is None:
            return stmt
        new_value = inline_expr(vm, stmt.value)
        return stmt if new_value is stmt.value else stmt.replace(value=new_value)

    if isinstance(stmt, ast.UnpackAssign):
        new_value = inline_expr(vm, stmt.value)
        return stmt if new_value is stmt.value else stmt.replace(value=new_value)

    if isinstance(stmt, ast.SetAttr):
        new_target = inline_expr(vm, stmt.target)
        new_value = inline_expr(vm, stmt.value)
        if new_target is stmt.target and new_value is stmt.value:
            return stmt
        return stmt.replace(target=new_target, value=new_value)

    if isinstance(stmt, ast.SetItem):
        new_target = inline_expr(vm, stmt.target)
        new_args = [inline_expr(vm, a) for a in stmt.args]
        new_value = inline_expr(vm, stmt.value)
        if (
            new_target is stmt.target
            and all(n is o for n, o in zip(new_args, stmt.args))
            and new_value is stmt.value
        ):
            return stmt
        return stmt.replace(target=new_target, args=new_args, value=new_value)

    # Raise, Pass, Break, Continue, AssignCell, Assert, AugAssign — recurse into
    # any Expr children via the generic path below.
    # For now, anything we don't specifically handle is returned unchanged
    # (conservative: we may miss inlining inside e.g. Assert, but that's fine).
    return stmt


def inline_expr(vm: "SPyVM", expr: ast.Expr) -> ast.Expr:
    """
    Recursively inline @force_inline calls inside an expression.

    The key case: if `expr` is an `ast.Call` whose callee is an
    `ast.FQNConst` pointing to a @force_inline W_ASTFunc, substitute the
    callee's return expression with the call-site args.
    """
    if isinstance(expr, ast.Call):
        # First recursively inline the arguments.
        new_args = [inline_expr(vm, a) for a in expr.args]
        new_func = inline_expr(vm, expr.func)

        # Check if the callee is a @force_inline function.
        if isinstance(new_func, ast.FQNConst):
            w_callee = vm.globals_w.get(new_func.fqn)
            if (
                isinstance(w_callee, W_ASTFunc)
                and w_callee.is_force_inline
                and w_callee.redshifted
            ):
                substituted = _substitute(vm, w_callee, new_args, expr)
                return inline_expr(vm, substituted)

        # Not a force_inline call: rebuild if anything changed.
        if new_func is expr.func and all(n is o for n, o in zip(new_args, expr.args)):
            return expr
        return expr.replace(func=new_func, args=new_args)

    # For all other expression types recurse into children.
    return _recurse_expr(vm, expr)


def _substitute(
    vm: "SPyVM",
    w_callee: W_ASTFunc,
    call_args: list[ast.Expr],
    call_node: ast.Call,
) -> ast.Expr:
    """
    Replace a call to a @force_inline function with its return expression,
    substituting each parameter name with the corresponding call-site argument.

    The callee body is exactly [Return(value=<expr>)].
    """
    assert isinstance(w_callee.funcdef.body[0], ast.Return)
    return_expr: ast.Expr = w_callee.funcdef.body[0].value

    param_names = [arg.name for arg in w_callee.funcdef.args]
    assert len(param_names) == len(call_args), (
        f"@force_inline arity mismatch for {w_callee.fqn}: "
        f"expected {len(param_names)} args, got {len(call_args)}"
    )

    # Map the symbol objects from the callee's symtable to the call-site exprs.
    symtable = w_callee.funcdef.symtable
    sym_to_expr: dict[int, ast.Expr] = {}  # id(sym) -> replacement
    for name, arg_expr in zip(param_names, call_args):
        sym = symtable.lookup(name)
        sym_to_expr[id(sym)] = arg_expr

    # Substitute and preserve the w_T of the original call node.
    result = _subst_expr(return_expr, sym_to_expr)
    # Propagate the call's result type onto the top-level node if it isn't set.
    if call_node.w_T is not None and result.w_T is None:
        result = result.replace(w_T=call_node.w_T)
    return result


def _subst_expr(expr: ast.Expr, sym_to_expr: dict[int, ast.Expr]) -> ast.Expr:
    """Recursively substitute NameLocalDirect nodes that match our param syms."""

    if isinstance(expr, ast.NameLocalDirect):
        replacement = sym_to_expr.get(id(expr.sym))
        if replacement is not None:
            # Keep the w_T from the original parameter reference so the tree
            # stays consistently typed.
            if expr.w_T is not None and replacement.w_T is None:
                return replacement.replace(w_T=expr.w_T)
            return replacement

    # Leaf nodes (Constant, FQNConst, StrConst, LocConst, etc.)
    if not expr.get_children():
        return expr

    # Recurse: rebuild only if something changed.
    return _rebuild_expr(expr, sym_to_expr)


def _rebuild_expr(expr: ast.Expr, sym_to_expr: dict[int, ast.Expr]) -> ast.Expr:
    """
    Rebuild an expression node, substituting inside all Expr children.
    Returns the same object if nothing changed.
    """
    changes: dict[str, object] = {}
    for f in expr.__dataclass_fields__.values():
        val = getattr(expr, f.name)
        if isinstance(val, ast.Expr):
            new_val = _subst_expr(val, sym_to_expr)
            if new_val is not val:
                changes[f.name] = new_val
        elif isinstance(val, list):
            new_list = _subst_list(val, sym_to_expr)
            if new_list is not val:
                changes[f.name] = new_list

    if not changes:
        return expr
    return expr.replace(**changes)


def _subst_list(items: list, sym_to_expr: dict[int, ast.Expr]) -> list:
    """Substitute inside a list of AST nodes. Returns same list if unchanged."""
    new_items = []
    changed = False
    for item in items:
        if isinstance(item, ast.Expr):
            new_item = _subst_expr(item, sym_to_expr)
            new_items.append(new_item)
            if new_item is not item:
                changed = True
        else:
            new_items.append(item)
    return new_items if changed else items


def _recurse_expr(vm: "SPyVM", expr: ast.Expr) -> ast.Expr:
    """
    Recurse into an arbitrary expression to find and inline any nested calls.
    """
    changes: dict[str, object] = {}
    for f in expr.__dataclass_fields__.values():
        val = getattr(expr, f.name)
        if isinstance(val, ast.Expr):
            new_val = inline_expr(vm, val)
            if new_val is not val:
                changes[f.name] = new_val
        elif isinstance(val, list):
            new_list = []
            list_changed = False
            for item in val:
                if isinstance(item, ast.Expr):
                    new_item = inline_expr(vm, item)
                    new_list.append(new_item)
                    if new_item is not item:
                        list_changed = True
                else:
                    new_list.append(item)
            if list_changed:
                changes[f.name] = new_list

    if not changes:
        return expr
    return expr.replace(**changes)
