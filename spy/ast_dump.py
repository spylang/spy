from typing import Any, Literal, Optional
import ast as py_ast
import spy.ast
from spy.textbuilder import TextBuilder

# Supported types of text coloring in AST printing
#  - Multi means red /blue / green / purple, done down to the token level.
#  - Redshift means only red and blue, at the expression level.
ColorMode = Literal['multi', 'redshift']

def dump(node: Any,
         *,
         use_colors: bool = True,
         fields_to_ignore: Any = (),
         hl: Any = None,
         color_mode: ColorMode = 'multi',
         ) -> str:
    dumper = Dumper(use_colors=use_colors, highlight=hl, color_mode=color_mode)
    dumper.fields_to_ignore += fields_to_ignore
    dumper.dump_anything(node)
    return dumper.build()

def pprint(node: Any, *, copy_to_clipboard: bool = False,
           hl: Optional[spy.ast.Node]=None, color_mode: ColorMode='multi') -> None:
    print(dump(node, hl=hl, color_mode=color_mode))
    if copy_to_clipboard:
        import pyperclip  # type: ignore
        out = dump(node, use_colors=False)
        pyperclip.copy(out)


class Dumper(TextBuilder):
    fields_to_ignore: tuple[str, ...]

    def __init__(self, *,
                 use_colors: bool,
                 highlight: Optional[spy.ast.Node] = None,
                 color_mode: ColorMode = 'multi'
                 ) -> None:
        super().__init__(use_colors=use_colors)
        self.highlight = highlight
        self.fields_to_ignore = ('loc', 'target_loc', 'target_locs',
                                 'loc_asname')
        self.color_mode = color_mode

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
        color = 'blue'
        # If color_mode is redshift, use node.color if available as saved
        # during redshifting
        if isinstance(node, spy.ast.Expr) and self.color_mode == 'redshift':
            color = node.color or color
        self._dump_node(node, name, fields, color=color)

    def dump_py_node(self, node: py_ast.AST) -> None:
        name = 'py:' + node.__class__.__name__
        fields = list(node.__class__._fields)
        fields = [f for f in fields if f not in self.fields_to_ignore]
        if isinstance(node, py_ast.Name):
            fields.append('is_var')
        color = 'turquoise' if self.color_mode == 'multi' else None
        self._dump_node(node, name, fields, color=color)

    def _dump_node(self, node: Any, name: str, fields: list[str], color: str) -> None:
        def is_complex(obj: Any) -> bool:
            return (isinstance(obj, (spy.ast.Node, py_ast.AST, list)) and
                    not isinstance(obj, py_ast.expr_context))
        values = [getattr(node, field) for field in fields]
        is_complex_field = [is_complex(value) for value in values]
        multiline = any(is_complex_field)
        #
        if node is self.highlight and self.color_mode == 'multi':
            color = 'red'
        self.write(name, color=color)
        self.write('(')
        if multiline:
            self.writeline('')
        with self.indent():
            for field, value in zip(fields, values):
                if field == 'color' and value is None:
                    continue
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
