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

    def visit_body(self, body: list[ast.Stmt]) -> list[ast.Stmt]:
        return list(body)

    def fresh_tmp(self, w_T: "W_Type") -> str:
        """
        Allocate a fresh local name of the given type: $v0, $v1, ...
        """
        name = f"$v{self.tmp_counter}"
        self.tmp_counter += 1
        self.new_locals[name] = w_T
        return name
