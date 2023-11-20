import typing
from typing import Any, Optional
import textwrap
import re
from dataclasses import dataclass
from spy.vm.object import W_Object, W_Type, spytype
from spy.textbuilder import ColorFormatter
from spy.util import print_diff

if typing.TYPE_CHECKING:
    from spy.vm.function import W_FuncType


RE_WHITESPACE = re.compile(r" +")

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
    'br_if',
    'br_while_not',
    'label',
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

    def copy(self) -> 'OpCode':
        return OpCode(self.name, *self.args)


@spytype('CodeObject')
class W_CodeObject(W_Object):
    name: str
    filename: str
    lineno: int
    body: list[OpCode]
    locals_w_types: dict[str, W_Type]

    def __init__(self, name: str, *,
                 filename: str = '', lineno: int = -1) -> None:
        self.name = name
        self.filename = filename
        self.lineno = lineno
        self.body = []
        self.locals_w_types = {}

    def __repr__(self) -> str:
        return f'<spy CodeObject {self.name}>'

    def declare_local(self, name: str, w_type: W_Type) -> None:
        assert name not in self.locals_w_types
        self.locals_w_types[name] = w_type

    def pp(self) -> None:
        """
        Pretty print
        """
        color = ColorFormatter(use_colors=True)
        name = color.set('green', self.name)
        #sig = color.set('red', self.w_functype.name)
        print(f'Disassembly of code {name}: {sig}')
        for name, w_type in self.locals_w_types.items():
            name = color.set('green', name)
            typename = color.set('red', w_type.name)
            print(f'    var {name}: {typename}')
        #
        print()
        body = self.dump(color)
        print(body)

    def dump(self, color: Optional[ColorFormatter] = None) -> str:
        if color is None:
            color = ColorFormatter(use_colors=False)

        # first, find all the branches and record the targets, for coloring
        all_br_targets = set()
        for op in self.body:
            if op.is_br():
                all_br_targets.add(op.args[0])
        #
        lines = []
        for i, op in enumerate(self.body):
            args = ', '.join([str(arg) for arg in op.args])
            if op.name == 'label':
                label_name, = op.args
                lines.append(color.set('yellow', f'{label_name}:'))
                continue
            #
            if op.name in ('load_local', 'store_local',
                           'load_global', 'store_global'):
                args = color.set('green', args)
            elif op.is_br() or op.name.startswith('mark_'):
                args = color.set('yellow', args)
            elif op.name == 'abort':
                args = repr(args)
            #
            lines.append((f'    {op.name:<15} {args}'))
        return '\n'.join(lines)


    def equals(self, expected: str) -> bool:
        """
        For tests. Ignore all the whitespace.
        """
        expected = textwrap.dedent(expected).strip()
        got = textwrap.dedent(self.dump()).strip()
        expected = RE_WHITESPACE.sub(" ", expected)
        got = RE_WHITESPACE.sub(" ", got)
        if expected == got:
            return True
        else:
            print_diff(expected, got, 'expected', 'got')
            return False
