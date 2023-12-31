# XXX KILL ME

import typing
import spy.ast
from spy.irgen import multiop
from spy.vm.builtins import B
if typing.TYPE_CHECKING:
    from spy.irgen.legacy_codegen import LegacyCodeGen

@multiop.GetItem(B.w_str, B.w_i32, w_restype=B.w_str)
def str_emit_getitem(cg: 'LegacyCodeGen', op: spy.ast.GetItem) -> None:
    cg.eval_expr(op.value)
    cg.eval_expr(op.index)
    cg.emit(op.loc, 'call_helper', 'StrGetItem', 2)
