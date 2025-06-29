from typing import Any, Optional
import ast as py_ast
import spy.ast
from spy.textbuilder import TextBuilder

def dump(node: Any,
         *,
         use_colors: bool = True,
         fields_to_ignore: Any = (),
         hl: Any = None,
         colorize: bool = False,
         ) -> str:
    dumper = Dumper(use_colors=use_colors, highlight=hl, colorize=colorize)
    dumper.fields_to_ignore += fields_to_ignore
    dumper.dump_anything(node)
    return dumper.build()

def pprint(node: Any, *, copy_to_clipboard: bool = False,
           hl: Optional[spy.ast.Node]=None, colorize: bool = False) -> None:
    print(dump(node, hl=hl, colorize=colorize))
    if copy_to_clipboard:
        import pyperclip  # type: ignore
        out = dump(node, use_colors=False)
        pyperclip.copy(out)


class Dumper(TextBuilder):
    fields_to_ignore: tuple[str, ...]

    def __init__(self, *,
                 use_colors: bool,
                 highlight: Optional[spy.ast.Node] = None,
                 colorize: bool = False
                 ) -> None:
        super().__init__(use_colors=use_colors)
        self.highlight = highlight
        self.fields_to_ignore = ('loc', 'target_loc', 'target_locs',
                                 'loc_asname')

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
        if isinstance(node, py_ast.Name):
            fields.append('is_var')
        self._dump_node(node, name, fields, color='turquoise')

    def _dump_node(self, node: Any, name: str, fields: list[str], color: str) -> None:
        def is_complex(obj: Any) -> bool:
            return (isinstance(obj, (spy.ast.Node, py_ast.AST, list)) and
                    not isinstance(obj, py_ast.expr_context))
        values = [getattr(node, field) for field in fields]
        is_complex_field = [is_complex(value) for value in values]
        multiline = any(is_complex_field)
        #
        if node is self.highlight:
            color = 'red'
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
