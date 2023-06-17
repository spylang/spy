from typing import Any, Iterator
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

    def __init__(self) -> None:
        self.level = 0
        self.lines = ['']
        self.fields_to_ignore = ('loc',)

    @contextmanager
    def indent(self) -> Iterator[None]:
        self.level += 1
        yield
        self.level -= 1

    def write(self, s: str) -> None:
        if self.lines[-1] == '':
            # add the indentation
            spaces = ' ' * (self.level * 4)
            self.lines[-1] = spaces
        self.lines[-1] += s

    def writeline(self, s: str) -> None:
        self.write(s)
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
        else:
            self.write(repr(obj))

    def dump_spy_node(self, node: spy.ast.Node) -> None:
        name = node.__class__.__name__
        self.writeline(f'{name}(')
        with self.indent():
            for attr in node.__class__.__dataclass_fields__:
                if attr in self.fields_to_ignore:
                    continue
                value = getattr(node, attr)
                self.write(f'{attr}=')
                self.dump_anything(value)
                self.writeline(',')
        self.write(')')

    def dump_py_node(self, py_node: py_ast.AST) -> None:
        name = py_node.__class__.__name__
        self.writeline(f'py:{name}(')
        with self.indent():
            for attr in py_node.__class__._fields:
                if attr in self.fields_to_ignore:
                    continue
                value = getattr(py_node, attr)
                self.write(f'{attr}=')
                self.dump_anything(value)
                self.writeline(',')
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
