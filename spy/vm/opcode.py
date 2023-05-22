# for now, each opcode is represented by its name. Very inefficient but we
# don't care for now. Eventually, we could migrate to a more proper bytecode
# or wordcode.
ALL_OPCODES = [
    'return',
    'i32_const',
]

class OpCode:

    def __init__(self, name, *args):
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

    def __init__(self, name, body):
        self.name = name
        self.body = body

    def __repr__(self):
        return f'<CodeObject {self.name}>'
