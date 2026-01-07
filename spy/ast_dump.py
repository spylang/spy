import ast as py_ast
from typing import TYPE_CHECKING, Any, Optional

import spy.ast
from spy.analyze.symtable import Color, Symbol
from spy.textbuilder import TextBuilder

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


def dump(
    node: Any,
    *,
    use_colors: bool = True,
    fields_to_ignore: Any = (),
    hl: Any = None,
    vm: Optional["SPyVM"] = None,
) -> str:
    dumper = Dumper(use_colors=use_colors, highlight=hl, vm=vm)
    dumper.fields_to_ignore += fields_to_ignore
    dumper.dump_anything(node)
    return dumper.build()


def pprint(
    node: Any,
    *,
    copy_to_clipboard: bool = False,
    hl: Optional[spy.ast.Node] = None,
    vm: Optional["SPyVM"] = None,
) -> None:
    print(dump(node, hl=hl, vm=vm))
    if copy_to_clipboard:
        import pyperclip  # type: ignore

        out = dump(node, use_colors=False)
        pyperclip.copy(out)


class Dumper(TextBuilder):
    fields_to_ignore: tuple[str, ...]
    vm: "SPyVM | None"

    def __init__(
        self,
        *,
        use_colors: bool,
        highlight: Optional[spy.ast.Node] = None,
        vm: Optional["SPyVM"] = None,
    ) -> None:
        super().__init__(use_colors=use_colors)
        self.highlight = highlight
        self.fields_to_ignore = (
            "loc",
            "target_loc",
            "body_loc",
            "target_locs",
            "loc_asname",
        )
        self.vm = vm

    def dump_anything(self, obj: Any) -> None:
        if isinstance(obj, spy.ast.Node):
            self.dump_spy_node(obj)
        elif isinstance(obj, py_ast.AST):
            self.dump_py_node(obj)
        elif type(obj) is list:
            self.dump_list(obj)
        elif type(obj) is Symbol:
            self.dump_Symbol(obj)
        elif type(obj) is str:
            self.write(repr(obj), color="green")
        else:
            self.write(repr(obj))

    def dump_spy_node(self, node: spy.ast.Node) -> None:
        name = node.__class__.__name__
        fields = list(node.__class__.__dataclass_fields__)
        fields = [f for f in fields if f not in self.fields_to_ignore]
        # Use turquoise text_color to distinguish from blue in colorize command
        self._dump_node(node, name, fields, text_color="turquoise")

    def dump_py_node(self, node: py_ast.AST) -> None:
        name = "py:" + node.__class__.__name__
        fields = list(node.__class__._fields)
        fields = [f for f in fields if f not in self.fields_to_ignore]
        if isinstance(node, py_ast.Name):
            fields.append("spy_varkind")
        # Use turquoise text_color to distinguish from blue in colorize command
        self._dump_node(node, name, fields, text_color="turquoise")

    def dump_Symbol(self, sym: Symbol) -> None:
        self.write(f"Symbol({sym.name!r}, {sym.varkind!r}, {sym.storage!r})")

    def _dump_node(
        self, node: Any, name: str, fields: list[str], text_color: Optional[str]
    ) -> None:
        def is_complex(obj: Any) -> bool:
            return isinstance(
                obj, (spy.ast.Node, py_ast.AST, list, Symbol)
            ) and not isinstance(obj, py_ast.expr_context)

        values = [getattr(node, field) for field in fields]
        is_complex_field = [is_complex(value) for value in values]
        multiline = any(is_complex_field)
        #
        if node is self.highlight:
            text_color = "red"
        # If the vm contains an ast_color_map, use the expression's color
        # as the text background color, and use the default text_color
        bg_color = None
        if self.vm and self.vm.ast_color_map:
            color: Optional[Color] = self.vm.ast_color_map.get(node, None)
            if color:
                bg_color = color
                text_color = None
        self.write(name, color=text_color, bg=bg_color)
        self.write("(")
        if multiline:
            self.writeline("")
        with self.indent():
            for field, value in zip(fields, values):
                is_last = field is fields[-1]
                self.write(f"{field}=")
                self.dump_anything(value)
                if multiline:
                    self.writeline(",")
                elif not is_last:
                    # single line
                    self.write(", ")
        self.write(")")

    def dump_list(self, lst: list[Any]) -> None:
        if lst == []:
            self.write("[]")
            return
        self.writeline("[")
        with self.indent():
            for item in lst:
                self.dump_anything(item)
                self.writeline(",")
        self.write("]")
