import typing
from typing import Any
from dataclasses import dataclass
from spy.fqn import FQN
from spy.vm.object import W_Object, W_Type, spytype
from spy.textbuilder import ColorFormatter

if typing.TYPE_CHECKING:
    from spy.vm.function import W_FunctionType

# for now, each opcode is represented by its name. Very inefficient but we
# don't care for now. Eventually, we could migrate to a more proper bytecode
# or wordcode.
#
# In particular, the 'line' opcode marks the location in the source code: it
# is a very inefficient encoding, so eventually we want to migrate to
# something like CPython's lnotab
ALL_OPCODES = [
    'line',
    'return',
    'abort',
    'mark_if_then',
    'mark_if_then_else',
    'mark_while',
    'load_const',
    'load_local',
    'load_global',
    'store_local',
    'store_global',
    'call_global',
    'call_helper',
    'i32_add',
    'i32_sub',
    'i32_mul',
    'i32_eq',
    'i32_neq',
    'i32_lt',
    'i32_lte',
    'i32_gt',
    'i32_gte',
    'pop_and_discard',
    'br',
    'br_if_not',
]

@dataclass
class OpCode:
    name: str
    args: tuple

    def __init__(self, name: str, *args: Any) -> None:
        """
        A generic opcode.

        Each opcode expects a specific number of args, it's up to the caller
        to ensure it's correct.

        A special case is passing ... (the ellipsis object) as the only arg:
        in this case, it means that the OpCode is not fully constructed, and
        can be amended later by calling set_args().
        """
        if name not in ALL_OPCODES:
            raise ValueError(f'Invalid opcode: {name}')
        self.name = name
        self.args = args

    def __repr__(self) -> str:
        if self.args:
            return f'<OpCode {self.name} {list(self.args)}>'
        else:
            return f'<OpCode {self.name}>'

    def is_br(self) -> bool:
        return self.name.startswith('br')

    def match(self, name: str, *args: Any) -> bool:
        if args == (...,):
            # match only the name
            return self.name == name
        else:
            # match also the args
            return self.name == name and self.args == args

    def set_args(self, *args: int) -> None:
        if self.args != (...,):
            raise ValueError('Cannot set args on a fully constructed op')
        self.args = args


@spytype('CodeObject')
class W_CodeObject(W_Object):
    fqn: FQN
    w_functype: 'W_FunctionType'
    filename: str
    lineno: int
    body: list[OpCode]
    locals_w_types: dict[str, W_Type]

    def __init__(self, fqn: FQN, *, w_functype: 'W_FunctionType',
                 filename: str = '', lineno: int = -1) -> None:
        # XXX this might be wrong? The fqn should be attached to the function,
        # not to the code object. With closures/generic, we could have the
        # same code object in multiple modules, I think?
        self.fqn = fqn
        self.w_functype = w_functype
        self.filename = filename
        self.lineno = lineno
        self.body = []
        self.locals_w_types = {}

    def __repr__(self) -> str:
        return f'<spy CodeObject {self.fqn}>'

    def declare_local(self, name: str, w_type: W_Type) -> None:
        assert name not in self.locals_w_types
        self.locals_w_types[name] = w_type

    def pp(self) -> None:
        """
        Pretty print
        """
        color = ColorFormatter(use_colors=True)
        name = color.set('green', self.fqn.fullname)
        sig = color.set('red', self.w_functype.name)
        print(f'Disassembly of code {name}: {sig}')
        for name, w_type in self.locals_w_types.items():
            name = color.set('green', name)
            typename = color.set('red', w_type.name)
            print(f'    var {name}: {typename}')
        #
        print()
        # first, find all the branches and record the targets, for coloring
        all_br_targets = set()
        for op in self.body:
            if op.is_br():
                all_br_targets.add(op.args[0])
        #
        for i, op in enumerate(self.body):
            line = [color.set('blue', op.name)]
            args = ', '.join([str(arg) for arg in op.args])
            if op.name in ('load_local', 'store_local', 'load_global', 'store_global'):
                args = color.set('green', args)
            elif op.is_br():
                args = color.set('red', args)
            elif op.name == 'abort':
                args = repr(args)
            #
            label = format(i, '>5')
            if i in all_br_targets:
                label = color.set('red', label)
            print(f'    {label} {op.name:<15} {args}')
