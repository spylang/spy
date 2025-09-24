from typing import Any
import ast as py_ast
import html

import spy.ast
from spy.analyze.symtable import Symbol


class DotDumper:
    """Dumper that generates Graphviz DOT format for AST nodes"""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.node_counter = 0
        self.node_ids: dict[int, str] = {}  # maps id(obj) to node_id
        self.edges: list[tuple[str, str, str]] = []  # (from_id, to_id, label)

    def build(self) -> str:
        output = ['digraph AST {']
        output.append('    rankdir=TB;')
        output.append('')

        # Add node definitions
        output.extend(self.lines)

        # Add edges
        if self.edges:
            output.append('')
            for from_id, to_id, label in self.edges:
                if label:
                    output.append(f'    {from_id} -> {to_id} [label="{label}"];')
                else:
                    output.append(f'    {from_id} -> {to_id};')

        output.append('}')
        return '\n'.join(output)

    def get_node_id(self, obj: Any) -> str:
        obj_id = id(obj)
        if obj_id not in self.node_ids:
            self.node_counter += 1
            self.node_ids[obj_id] = f'node{self.node_counter}'
        return self.node_ids[obj_id]

    def dump_anything(self, obj: Any) -> str:
        if isinstance(obj, spy.ast.Node):
            return self.dump_spy_node(obj)
        elif isinstance(obj, py_ast.AST):
            return self.dump_py_node(obj)
        elif isinstance(obj, list):
            return self.dump_list(obj)
        elif isinstance(obj, Symbol):
            return self.dump_symbol(obj)
        else:
            # For simple values, create a leaf node
            node_id = self.get_node_id(obj)
            label = html.escape(repr(obj), quote=True)
            self.lines.append(f'    {node_id} [label="{label}", shape=oval];')
            return node_id

    def dump_spy_node(self, node: spy.ast.Node) -> str:
        node_id = self.get_node_id(node)
        name = node.__class__.__name__
        fields = list(node.__class__.__dataclass_fields__)
        fields = [f for f in fields if f not in ('loc', 'target_loc', 'target_locs', 'loc_asname')]

        # Separate complex fields from simple attributes
        complex_fields = []
        attributes = []

        for field in fields:
            value = getattr(node, field)
            if value is not None:
                if isinstance(value, (spy.ast.Node, py_ast.AST, list, Symbol)):
                    complex_fields.append((field, value))
                else:
                    attributes.append(f"{field}={repr(value)}")

        # Create node label with HTML formatting - use black for node names
        label_parts = [f'<B>{name}</B>']
        for attr in attributes:
            if '=' in attr:
                field_name, field_value = attr.split('=', 1)
                # Use same colors as stdout: strings=green, node names=turquoise, others=default
                # Escape the field value content but keep HTML tags unescaped
                escaped_field_value = html.escape(field_value, quote=True)
                if field_value.startswith("'") and field_value.endswith("'"):
                    colored_value = f'<FONT COLOR="#228B22">{escaped_field_value}</FONT>'  # darker green
                elif field_value.isdigit() or (field_value.startswith('-') and field_value[1:].isdigit()):
                    colored_value = f'<FONT COLOR="#0080FF">{escaped_field_value}</FONT>'  # blue
                else:
                    colored_value = f'<FONT COLOR="#666666">{escaped_field_value}</FONT>'  # gray
                label_parts.append(f'{html.escape(field_name, quote=True)}={colored_value}')
            else:
                label_parts.append(attr)

        if len(label_parts) > 1:
            html_label = '<BR/>'.join(label_parts)
        else:
            html_label = label_parts[0]

        self.lines.append(f'    {node_id} [label=<{html_label}>, shape=oval];')

        # Add edges to complex child nodes
        for field, value in complex_fields:
            child_id = self.dump_anything(value)
            self.edges.append((node_id, child_id, field))

        return node_id

    def dump_py_node(self, node: py_ast.AST) -> str:
        node_id = self.get_node_id(node)
        name = 'py:' + node.__class__.__name__
        fields = list(node.__class__._fields)
        fields = [f for f in fields if f not in ('loc', 'target_loc', 'target_locs', 'loc_asname')]

        if isinstance(node, py_ast.Name):
            fields.append('is_var')

        # Separate complex fields from simple attributes
        complex_fields = []
        attributes = []

        for field in fields:
            if hasattr(node, field):
                value = getattr(node, field)
                if value is not None:
                    if isinstance(value, (spy.ast.Node, py_ast.AST, list, Symbol)):
                        complex_fields.append((field, value))
                    else:
                        attributes.append(f"{field}={repr(value)}")

        # Create node label with HTML formatting - use black for node names
        label_parts = [f'<B>{name}</B>']
        for attr in attributes:
            if '=' in attr:
                field_name, field_value = attr.split('=', 1)
                # Use same colors as stdout: strings=green, node names=turquoise, others=default
                # Escape the field value content but keep HTML tags unescaped
                escaped_field_value = html.escape(field_value, quote=True)
                if field_value.startswith("'") and field_value.endswith("'"):
                    colored_value = f'<FONT COLOR="#228B22">{escaped_field_value}</FONT>'  # darker green
                elif field_value.isdigit() or (field_value.startswith('-') and field_value[1:].isdigit()):
                    colored_value = f'<FONT COLOR="#0080FF">{escaped_field_value}</FONT>'  # blue
                else:
                    colored_value = f'<FONT COLOR="#666666">{escaped_field_value}</FONT>'  # gray
                label_parts.append(f'{html.escape(field_name, quote=True)}={colored_value}')
            else:
                label_parts.append(attr)

        if len(label_parts) > 1:
            html_label = '<BR/>'.join(label_parts)
        else:
            html_label = label_parts[0]

        self.lines.append(f'    {node_id} [label=<{html_label}>, shape=oval];')

        # Add edges to complex child nodes
        for field, value in complex_fields:
            child_id = self.dump_anything(value)
            self.edges.append((node_id, child_id, field))

        return node_id

    def dump_list(self, lst: list[Any]) -> str:
        list_id = self.get_node_id(lst)

        if not lst:
            self.lines.append(f'    {list_id} [label="list []", shape=rectangle];')
            return list_id

        self.lines.append(f'    {list_id} [label="list [{len(lst)}]", shape=rectangle];')

        for i, item in enumerate(lst):
            child_id = self.dump_anything(item)
            self.edges.append((list_id, child_id, f'[{i}]'))

        return list_id

    def dump_symbol(self, sym: Symbol) -> str:
        node_id = self.get_node_id(sym)
        label = html.escape(f'Symbol({sym.name!r}, {sym.color!r}, {sym.varkind!r}, {sym.storage!r})', quote=True)
        self.lines.append(f'    {node_id} [label="{label}", shape=hexagon];')
        return node_id


def dump_dot(node: Any) -> str:
    """Generate Graphviz DOT format for the AST"""
    dumper = DotDumper()
    dumper.dump_anything(node)
    return dumper.build()


def pprint_dot(node: Any) -> None:
    """Print AST in Graphviz DOT format"""
    print(dump_dot(node))