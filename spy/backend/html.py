import dataclasses
import json
from typing import Any, Literal, Optional

import spy.ast
from spy import ROOT
from spy.analyze.symtable import Color, Symbol
from spy.backend.spy import SPyBackend
from spy.vm.vm import SPyVM

SpyastJs = Literal["cdn", "inline"]

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

# Nodes that start expanded.
EXPAND_BY_DEFAULT = frozenset({"Module", "FuncDef", "GlobalFuncDef"})

_SPYAST_JS = ROOT / ".." / "playground" / "spyast" / "spyast.js"


def _label_str(val: Any) -> str:
    if isinstance(val, Symbol):
        return val.name
    if isinstance(val, str):
        return repr(val)
    return str(val)


def _get_src(node: spy.ast.Node) -> str:
    try:
        src = node.loc.get_src()
    except (ValueError, AttributeError):
        return ""
    # get_src strips col_start from the first line but not subsequent ones, dedent
    # manually
    indent = node.loc.col_start
    if indent == 0:
        return src
    prefix = " " * indent
    lines = src.split("\n")
    dedented = [lines[0]] + [
        line[indent:] if line.startswith(prefix) else line for line in lines[1:]
    ]
    return "\n".join(dedented)


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


def _spyast_js_tag(mode: SpyastJs) -> str:
    if mode == "cdn":
        url = "https://cdn.jsdelivr.net/gh/spy-lang/spy/playground/spyast/spyast.js"
        return f'<script src="{url}"></script>'
    else:
        js_code = _SPYAST_JS.read()
        return f"<script>\n{js_code}\n</script>"


class HTMLBackend:
    def __init__(
        self,
        spyast_js: SpyastJs = "cdn",
        vm: Optional[SPyVM] = None,
        is_redshifted: bool = False,
        ast_color_map: Optional[dict[spy.ast.Node, Color]] = None,
    ) -> None:
        self.spyast_js = spyast_js
        self.spy_backend: Optional[SPyBackend] = None
        self.ast_color_map = ast_color_map
        if is_redshifted:
            assert vm is not None
            self.spy_backend = SPyBackend(vm)

    def _get_src_colors(self, node: spy.ast.Node) -> list[dict[str, Any]]:
        if self.ast_color_map is None:
            return []
        parent_line = node.loc.line_start
        indent = node.loc.col_start
        colors = []
        for child in node.walk():
            if child is node:
                continue
            color = self.ast_color_map.get(child)
            if color is None:
                continue
            # only single-line children for now
            if child.loc.line_start != child.loc.line_end:
                continue
            colors.append(
                {
                    "line": child.loc.line_start - parent_line,
                    "start": child.loc.col_start - indent,
                    "end": child.loc.col_end - indent,
                    "color": color,
                }
            )
        return colors

    def node_to_dict(self, node: spy.ast.Node) -> dict[str, Any]:
        typename = type(node).__name__
        is_expr = isinstance(node, spy.ast.Expr)

        children = []
        for f in dataclasses.fields(node):  # type: ignore[arg-type]
            if f.name in FIELDS_TO_IGNORE:
                continue
            val = getattr(node, f.name)
            if isinstance(val, spy.ast.Node):
                children.append({"attr": f.name, "node": self.node_to_dict(val)})
            elif isinstance(val, list):
                for i, item in enumerate(val):
                    attr = f"{f.name}[{i}]" if len(val) > 1 else f.name
                    if isinstance(item, spy.ast.Node):
                        children.append({"attr": attr, "node": self.node_to_dict(item)})
                    else:
                        children.append({"attr": attr, "node": _scalar_leaf(item)})
            elif val is not None:
                children.append({"attr": f.name, "node": _scalar_leaf(val)})

        if self.spy_backend is not None and is_expr:
            src = self.spy_backend.fmt_expr(node)
        else:
            src = _get_src(node)

        src_colors = self._get_src_colors(node)

        if self.ast_color_map is not None:
            node_color = self.ast_color_map.get(node)
            if node_color == "red":
                color = "red"
            elif node_color == "blue":
                color = "blue"
            else:
                color = "default"
        else:
            color = "amber" if is_expr else "default"

        sr = node.shortrepr()
        label = f"{typename}: {sr}" if sr is not None else typename
        result: dict[str, Any] = {
            "label": label,
            "expr": is_expr,
            "src": src,
            "shape": "expr" if is_expr else "stmt",
            "color": color,
            "children": children,
        }
        if src_colors:
            result["src_colors"] = src_colors
        if typename in EXPAND_BY_DEFAULT:
            result["startExpanded"] = True
        return result

    def generate(
        self,
        sections: list[tuple[str, spy.ast.Node]],
    ) -> str:
        js_tag = _spyast_js_tag(self.spyast_js)

        renders = []
        for i, (title, node) in enumerate(sections):
            ast_json = json.dumps(self.node_to_dict(node))
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
