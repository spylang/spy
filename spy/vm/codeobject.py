import typing
from typing import Any, Optional
import textwrap
import re
from dataclasses import dataclass
from spy import ast
from spy.location import Loc
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
    'declare_local',
    'load_const',
    'load_local',
    'load_global', # XXX kill?
    'load_nonlocal',
    'store_local',
    'store_global', # XXX kill?
    'add_global',   # same as store_global, but also declares it
    'load_nonlocal',
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
    'dup',
    'make_func_type',
    'make_function',
    'make_function_ast',
]

@dataclass
class OpCode:
    name: str
    loc: Loc
    args: tuple

    def __init__(self, name: str, loc: Loc, *args: Any) -> None:
        """
        A generic opcode.

        Each opcode expects a specific number of args, it's up to the caller
        to ensure it's correct.
        """
        if name not in ALL_OPCODES:
            raise ValueError(f'Invalid opcode: {name}')
        self.name = name
        self.loc = loc
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


def OpCodeWithFakeLoc(name: str, *args: Any) -> OpCode:
    """
    Same as OpCode, but uses a fake loc. Useful for tests.
    """
    return OpCode(name, Loc.fake(), *args)


@spytype('CodeObject')
class W_CodeObject(W_Object):
    name: str
    filename: str
    lineno: int
    body: list[OpCode]
    locals_w_types: dict[str, W_Type]
    end_prologue: int

    def __init__(self, *,
                 name: str,
                 filename: str,
                 lineno: int,
                 retloc: Loc,
                 arglocs: list[Loc],
                 ) -> None:
        self.name = name
        self.filename = filename
        self.lineno = lineno
        self.retloc = retloc
        self.arglocs = arglocs
        self.body = []
        self.locals_w_types = {} # XXX kill this eventually
        self.end_prologue = -1   # XXX kill this eventually

    @classmethod
    def from_funcdef(cls, funcdef: ast.FuncDef) -> 'W_CodeObject':
        retloc = funcdef.return_type.loc
        arglocs = [arg.loc for arg in funcdef.args]
        return cls(
            name = funcdef.name,
            filename = funcdef.loc.filename,
            lineno = funcdef.loc.line_start,
            retloc = retloc,
            arglocs = arglocs
        )

    @classmethod
    def for_tests(cls, name: str, n_args: int) -> 'W_CodeObject':
        return cls(
            name = name,
            filename = '',
            lineno = -1,
            retloc = Loc.fake(),
            arglocs = [Loc.fake()] * n_args
        )

    def __repr__(self) -> str:
        return f'<spy CodeObject {self.name}>'

    def declare_local(self, name: str, w_type: W_Type) -> None:
        """
        XXX kill this eventually. See also codegen.add_local_variables
        """
        assert name not in self.locals_w_types
        self.locals_w_types[name] = w_type

    def mark_end_prologue(self) -> None:
        self.end_prologue = len(self.body)

    def pp(self) -> None:
        """
        Pretty print
        """
        color = ColorFormatter(use_colors=True)
        name = color.set('green', self.name)
        print(f'Disassembly of code {name}:')
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
            lines.append(f'    {op.name:<15} {args}'.strip())
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
