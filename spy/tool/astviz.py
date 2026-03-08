import dataclasses
import json
from pathlib import Path
from typing import Any, Literal

import spy.ast
from spy.analyze.symtable import Symbol
from spy.fqn import FQN
from spy.vm.function import W_ASTFunc
from spy.vm.vm import SPyVM

SpyastJs = Literal["cdn", "local"]

FIELDS_TO_IGNORE = frozenset(
    {
        "loc",
        "target_loc",
        "body_loc",
        "target_locs",
        "loc_asname",
        "symtable",
        "w_T",
        "docstring",
        "seq",
    }
)

# For each typename, which plain scalar fields to append to the label (in order).
LABEL_FIELDS: dict[str, list[str]] = {
    "Name": ["id"],
    "BinOp": ["op"],
    "CmpOp": ["op"],
    "UnaryOp": ["op"],
    "AugAssign": ["op"],
    "AssignExpr": [],
    "FuncDef": ["color", "name"],
    "FuncArg": ["name", "kind"],
    "ClassDef": ["kind", "name"],
    "Constant": ["value"],
    "StrConst": ["value"],
    "Import": ["asname"],
}

# Nodes that start expanded.
EXPAND_BY_DEFAULT = frozenset({"Module", "FuncDef", "GlobalFuncDef"})

# Repo root: spy/tool/astviz.py → spy/tool/ → spy/ → <repo root>
_REPO_ROOT = Path(__file__).parents[2]


def _label_str(val: Any) -> str:
    # Symbol objects are verbose; just show the variable name.
    if isinstance(val, Symbol):
        return val.name
    return str(val)


def _get_src(node: spy.ast.Node) -> str:
    try:
        return node.loc.get_src()
    except (ValueError, AttributeError):
        return ""


def _scalar_leaf(val: Any) -> dict[str, Any]:
    s = _label_str(val)
    return {
        "label": s,
        "expr": True,
        "src": s,
        "shape": "leaf",
        "color": "emerald",
        "children": [],
    }


def node_to_dict(node: spy.ast.Node) -> dict[str, Any]:
    typename = type(node).__name__
    is_expr = isinstance(node, spy.ast.Expr)
    label_field_names = LABEL_FIELDS.get(typename, [])

    label_parts = [typename]
    for fname in label_field_names:
        val = getattr(node, fname, None)
        if val is not None:
            label_parts.append(_label_str(val))
    label = " ".join(label_parts)

    children = []
    for f in dataclasses.fields(node):  # type: ignore[arg-type]
        if f.name in FIELDS_TO_IGNORE or f.name in label_field_names:
            continue
        val = getattr(node, f.name)
        if isinstance(val, spy.ast.Node):
            children.append({"attr": f.name, "node": node_to_dict(val)})
        elif isinstance(val, list):
            for i, item in enumerate(val):
                attr = f"{f.name}[{i}]" if len(val) > 1 else f.name
                if isinstance(item, spy.ast.Node):
                    children.append({"attr": attr, "node": node_to_dict(item)})
                else:
                    children.append({"attr": attr, "node": _scalar_leaf(item)})
        elif val is not None:
            children.append({"attr": f.name, "node": _scalar_leaf(val)})

    result: dict[str, Any] = {
        "label": label,
        "expr": is_expr,
        "src": _get_src(node),
        "shape": "expr" if is_expr else "stmt",
        "color": "amber" if is_expr else "blue",
        "children": children,
    }
    if typename in EXPAND_BY_DEFAULT:
        result["startExpanded"] = True
    return result


def _spyast_js_tag(mode: SpyastJs) -> str:
    if mode == "cdn":
        url = "https://cdn.jsdelivr.net/gh/spy-lang/spy/playground/spyast/spyast.js"
        return f'<script src="{url}"></script>'
    else:
        local_path = _REPO_ROOT / "playground" / "spyast" / "spyast.js"
        return f'<script src="{local_path}"></script>'


def generate_html(
    sections: list[tuple[str, spy.ast.Node]],
    spyast_js: SpyastJs = "cdn",
) -> str:
    js_tag = _spyast_js_tag(spyast_js)

    renders = []
    for i, (title, node) in enumerate(sections):
        ast_json = json.dumps(node_to_dict(node))
        svg_id = f"diagram_{i}"
        renders.append(
            f"  <h2>{title}</h2>\n"
            f'  <svg id="{svg_id}"></svg>\n'
            f"  <script>SPyAstViz.render("
            f"document.getElementById({svg_id!r}), {ast_json});</script>"
        )

    body = "\n".join(renders)
    return f"""\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>AST Visualizer</title>
</head>
<body style="background:#f8fafc; padding:20px; font-family:sans-serif;">
{js_tag}
{body}
</body>
</html>
"""


def dump_html(vm: SPyVM, modname: str, spyast_js: SpyastJs) -> str:
    """
    Build an HTML page visualizing all red W_ASTFuncs in the given module.
    Returns the HTML string.
    """
    sections = []
    for fqn, w_obj in vm.fqns_by_modname(modname):
        if isinstance(w_obj, W_ASTFunc) and w_obj.color == "red" and w_obj.fqn == fqn:
            sections.append((str(fqn), w_obj.funcdef))
    return generate_html(sections, spyast_js)
