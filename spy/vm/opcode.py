# for now, each opcode is represented by its name. Very inefficient but we
# don't care for now. Eventually, we could migrate to a more proper bytecode
# or wordcode.
ALL_OPCODES = [
    'return',
    'i32_const',
    'i32_add',
]

class OpCode:
    name: str
    args: tuple

    def __init__(self, name: str, *args) -> None:
        if name not in ALL_OPCODES:
            raise ValueError(f'Invalid opcode: {name}')
        self.name = name
        self.args = args

    def __repr__(self):
        if self.args:
            return f'<OpCode {self.name} {list(self.args)}>'
        else:
            return f'<OpCode {self.name}>'



class CodeObject:
    name: str
    body: list[OpCode]

    def __init__(self, name: str, body: list[OpCode]):
        self.name = name
        self.body = body

    def __repr__(self):
        return f'<CodeObject {self.name}>'
