from typing import Any, Iterator, Optional
from contextlib import contextmanager
import ast as py_ast
import spy.ast

def dump(node: Any) -> str:
    dumper = Dumper()
    dumper.dump_anything(node)
    return dumper.build()

def pprint(node: Any) -> None:
    print(dump(node))


# monkey-patch python's AST to add a pp() method
py_ast.AST.pp = pprint  # type:ignore


class Dumper:
    level: int
    lines: list[str]
    fields_to_ignore: tuple[str, ...]
    use_colors: bool

    def __init__(self, use_colors: bool = True) -> None:
        self.level = 0
        self.lines = ['']
        self.use_colors = use_colors
        self.fields_to_ignore = ('loc',)

    @contextmanager
    def indent(self) -> Iterator[None]:
        self.level += 1
        yield
        self.level -= 1

    def write(self, s: str, *, color: Optional[str] = None) -> None:
        if color and self.use_colors:
            s = Color.set(color, s)
        if self.lines[-1] == '':
            # add the indentation
            spaces = ' ' * (self.level * 4)
            self.lines[-1] = spaces
        self.lines[-1] += s

    def writeline(self, s: str, *, color: Optional[str] = None) -> None:
        self.write(s, color=color)
        self.lines.append('')

    def build(self) -> str:
        return '\n'.join(self.lines)

    def dump_anything(self, obj: Any) -> None:
        if isinstance(obj, spy.ast.Node):
            self.dump_spy_node(obj)
        elif isinstance(obj, py_ast.AST):
            self.dump_py_node(obj)
        elif type(obj) is list:
            self.dump_list(obj)
        elif type(obj) is str:
            self.write(repr(obj), color='green')
        else:
            self.write(repr(obj))

    def dump_spy_node(self, node: spy.ast.Node) -> None:
        name = node.__class__.__name__
        fields = list(node.__class__.__dataclass_fields__)
        fields = [f for f in fields if f not in self.fields_to_ignore]
        self._dump_node(node, name, fields, color='blue')

    def dump_py_node(self, node: py_ast.AST) -> None:
        name = 'py:' + node.__class__.__name__
        fields = list(node.__class__._fields)
        fields = [f for f in fields if f not in self.fields_to_ignore]
        self._dump_node(node, name, fields, color='turquoise')

    def _dump_node(self, node: Any, name: str, fields: list[str], color: str) -> None:
        def is_complex(obj: Any) -> bool:
            return isinstance(obj, (spy.ast.Node, py_ast.AST, list))
        values = [getattr(node, field) for field in fields]
        is_complex_field = [is_complex(value) for value in values]
        multiline = any(is_complex_field)
        #
        self.write(name, color=color)
        self.write('(')
        if multiline:
            self.writeline('')
        with self.indent():
            for field, value in zip(fields, values):
                is_last = (field is fields[-1])
                self.write(f'{field}=')
                self.dump_anything(value)
                if multiline:
                    self.writeline(',')
                elif not is_last:
                    # single line
                    self.write(', ')
        self.write(')')

    def dump_list(self, lst: list[Any]) -> None:
        if lst == []:
            self.write('[]')
            return
        self.writeline('[')
        with self.indent():
            for item in lst:
                self.dump_anything(item)
                self.writeline(',')
        self.write(']')


class Color:
    black = '30'
    darkred = '31'
    darkgreen = '32'
    brown = '33'
    darkblue = '34'
    purple = '35'
    teal = '36'
    lightgray = '37'
    darkgray = '30;01'
    red = '31;01'
    green = '32;01'
    yellow = '33;01'
    blue = '34;01'
    fuchsia = '35;01'
    turquoise = '36;01'
    white = '37;01'

    @classmethod
    def set(cls, color: str, string: str) -> str:
        try:
            color = getattr(cls, color)
        except AttributeError:
            pass
        return '\x1b[%sm%s\x1b[00m' % (color, string)
