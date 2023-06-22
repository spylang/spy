import typing
from typing import Any
from spy.vm.object import W_Object, W_Type, spytype

if typing.TYPE_CHECKING:
    from spy.vm.function import W_FunctionType

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
    w_functype: 'W_FunctionType'
    filename: str
    body: list[OpCode]
    locals_w_types: dict[str, W_Type]

    def __init__(self, name: str, *, w_functype: 'W_FunctionType',
                 filename: str = '') -> None:
        self.name = name
        self.w_functype = w_functype
        self.filename = filename
        self.body = []
        self.locals_w_types = {}
        for param in w_functype.params:
            self.declare_local(param.name, param.w_type)

    def __repr__(self) -> str:
        return f'<spy CodeObject {self.name}>'

    def declare_local(self, name: str, w_type: W_Type) -> None:
        assert name not in self.locals_w_types
        self.locals_w_types[name] = w_type
