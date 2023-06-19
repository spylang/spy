from typing import Any
from spy.vm.object import W_Object, W_Type, spytype

# for now, each opcode is represented by its name. Very inefficient but we
# don't care for now. Eventually, we could migrate to a more proper bytecode
# or wordcode.
ALL_OPCODES = [
    'return',
    'const_load',
    'i32_add',
    'i32_sub',
    'local_set',
    'local_get',
    'global_set',
    'global_get',
]

class OpCode:
    name: str
    args: tuple

    def __init__(self, name: str, *args: Any) -> None:
        if name not in ALL_OPCODES:
            raise ValueError(f'Invalid opcode: {name}')
        self.name = name
        self.args = args

    def __repr__(self) -> str:
        if self.args:
            return f'<OpCode {self.name} {list(self.args)}>'
        else:
            return f'<OpCode {self.name}>'


@spytype('CodeObject')
class W_CodeObject(W_Object):
    name: str
    filename: str
    body: list[OpCode]
    params: tuple[str, ...]
    locals_w_types: dict[str, W_Type]
    w_restype: W_Type

    def __init__(self, name: str, *, w_restype: W_Type, filename: str = '') -> None:
        self.name = name
        self.filename = filename
        self.body = []
        self.params = ()
        self.locals_w_types = {}
        self.w_restype = w_restype

    def __repr__(self) -> str:
        return f'<spy CodeObject {self.name}>'
