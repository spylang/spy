"""
SPy `posix` module.
"""

from typing import TYPE_CHECKING, Annotated
from spy.vm.primitive import W_I32
from spy.vm.object import W_Type
from spy.vm.w import W_Object
from spy.vm.registry import ModuleRegistry
from spy.vm.member import Member
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

POSIX = ModuleRegistry('posix')

@POSIX.builtin_type('TerminalSize')
class W_TerminalSize(W_Object):
    __spy_storage_category__ = 'value'

    w_columns: Annotated[W_I32, Member('columns')]
    w_lines: Annotated[W_I32, Member('lines')]

    def __init__(self, columns: int, lines: int) -> None:
        self.w_columns = W_I32(columns)
        self.w_lines = W_I32(lines)

    def spy_key(self, vm: 'SPyVM') -> tuple:
        return ('TerminalSize', self.w_columns.value, self.w_lines.value)

@POSIX.builtin_func
def w_get_terminal_size(vm: 'SPyVM') -> W_TerminalSize:
    import os
    try:
        size = os.get_terminal_size()
        return W_TerminalSize(size.columns, size.lines)
    except OSError:
        # Fallback when no terminal is available (e.g., in tests)
        return W_TerminalSize(80, 24)
