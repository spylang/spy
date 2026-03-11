"""
Example code for how to visualize toyast.py with spyast.js.

THIS FILE IS NOT A FUNCTIONAL PART OF SPy
"""

import dataclasses
import json

from toyast import EXAMPLE, Expr, Module, Node, UnaryOp

# Which string field to append to the type name to form the label.
# Nodes not listed here use just the type name as label.
LABEL_FIELD = {
    "BinOp": "op",
    "UnaryOp": "op",
    "Const": "value",
    "Name": "name",
    "FuncDef": "name",
    "FuncArg": "name",
}

# String fields that should be rendered as a Name leaf child node
# rather than being silently ignored.
STR_AS_NAME = {
    "Assign": {"target"},
    "FuncDef": {"name"},
    "FuncArg": {"name"},
}

# Nodes that start expanded (all others start collapsed).
EXPAND_BY_DEFAULT = {"Module"}


def name_leaf(name):
    return {
        "type": "Name",
        "src": name,
        "label": name,
        "expr": True,
        "shape": "leaf",
        "color": "emerald",
        "children": [],
    }


def label_of(node):
    typename = type(node).__name__
    key = LABEL_FIELD.get(typename)
    return f"{typename} {getattr(node, key)}" if key else typename


def to_dict(node):
    typename = type(node).__name__
    str_as_name = STR_AS_NAME.get(typename, set())
    children = []

    for field in dataclasses.fields(node):
        val = getattr(node, field.name)
        if field.name in str_as_name:
            children.append({"attr": field.name, "node": name_leaf(val)})
        elif isinstance(val, Node):
            children.append({"attr": field.name, "node": to_dict(val)})
        elif isinstance(val, list) and val and isinstance(val[0], Node):
            for i, item in enumerate(val):
                attr = f"{field.name}[{i}]" if len(val) > 1 else field.name
                children.append({"attr": attr, "node": to_dict(item)})

    result = {
        "type": typename,
        "src": node.src,
        "label": label_of(node),
        "expr": isinstance(node, Expr),
        "shape": "expr" if isinstance(node, Expr) else "stmt",
        "color": "amber" if isinstance(node, Expr) else "blue",
        "children": children,
    }
    if typename in EXPAND_BY_DEFAULT:
        result["startExpanded"] = True
    return result


ast_json = json.dumps(to_dict(EXAMPLE))

html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>AST Visualizer</title>
</head>
<body style="background:#f8fafc; padding:20px; font-family:sans-serif;">
  <h2>AST: EXAMPLE</h2>
  <svg id="diagram"></svg>
  <script src="spyast.js"></script>
  <script>SPyAstViz.render(document.getElementById('diagram'), {ast_json});</script>
</body>
</html>
"""

import pathlib

here = pathlib.Path(__file__).parent
with open(here / "output.html", "w") as f:
    f.write(html)

print("Written output.html")
