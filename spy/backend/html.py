# WARNING: this file has written by autonomous coding assistans for the major part.

import dataclasses
import json
import textwrap
from typing import Any, Literal, Optional, Sequence

import spy.ast
from spy import ROOT
from spy.analyze.symtable import Color, Symbol
from spy.backend.spy import SPyBackend
from spy.util import build_char_color_map, encode_color_map
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
    # ClassDef/GlobalClassDef.loc points only to "class X:", use body_loc to include the body
    if isinstance(node, spy.ast.ClassDef):
        loc = node.body_loc
    elif isinstance(node, spy.ast.GlobalClassDef):
        loc = node.classdef.body_loc
    else:
        loc = node.loc
    try:
        src = loc.get_src()
    except (ValueError, AttributeError):
        return ""
    return textwrap.dedent(src)


def _scalar_leaf(val: Any) -> dict[str, Any]:
    s = _label_str(val)
    return {
        "label": s,
        "expr": True,
        "src": None,
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
        assert isinstance(js_code, str)
        return f"<script>\n{js_code}\n</script>"


class HTMLBackend:
    def __init__(
        self,
        spyast_js: SpyastJs = "cdn",
        vm: Optional[SPyVM] = None,
        is_redshifted: bool = False,
        ast_color_map: Optional[dict[spy.ast.Node, Color]] = None,
        start_all_collapsed: bool = False,
    ) -> None:
        self.spyast_js = spyast_js
        self.spy_backend: Optional[SPyBackend] = None
        self.ast_color_map = ast_color_map
        self.start_all_collapsed = start_all_collapsed
        self.is_redshifted = is_redshifted
        if is_redshifted:
            assert vm is not None
            self.spy_backend = SPyBackend(vm)

    def _get_src_colors(self, node: spy.ast.Node, src: str) -> str:
        if self.ast_color_map is None or not src:
            return ""
        src_lines = src.split("\n")
        num_lines = len(src_lines)
        parent_line = node.loc.line_start
        indent = node.loc.col_start

        # Build flat line-start offsets for converting (line_idx, col) to flat position
        line_offsets: list[int] = []
        offset = 0
        for src_line in src_lines:
            line_offsets.append(offset)
            offset += len(src_line) + 1  # +1 for \n

        spans: list[tuple[int, int, str]] = []
        for child in node.walk():
            if child is node:
                continue
            color = self.ast_color_map.get(child)
            if color is None:
                continue
            # only single-line children for now
            if child.loc.line_start != child.loc.line_end:
                continue
            line_idx = child.loc.line_start - parent_line
            if line_idx < 0 or line_idx >= num_lines:
                continue
            start = child.loc.col_start - indent
            end = child.loc.col_end - indent
            if start < 0 or end > len(src_lines[line_idx]):
                continue
            flat_start = line_offsets[line_idx] + start
            flat_end = line_offsets[line_idx] + end
            spans.append((flat_start, flat_end, color))

        return encode_color_map(build_char_color_map(src, spans))

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
                    attr = f"{f.name}[{i}]"
                    if isinstance(item, spy.ast.Node):
                        children.append({"attr": attr, "node": self.node_to_dict(item)})
                    else:
                        children.append({"attr": attr, "node": _scalar_leaf(item)})
            else:
                children.append({"attr": f.name, "node": _scalar_leaf(val)})

        if self.spy_backend is not None and isinstance(node, spy.ast.Expr):
            src = self.spy_backend.fmt_expr(node)
        else:
            src = _get_src(node)

        # try to colorize the source code, but don't do that for redshifted ASTs.
        src_colors = ""
        if not self.is_redshifted:
            src_colors = self._get_src_colors(node, src)

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
        if not self.start_all_collapsed and typename in EXPAND_BY_DEFAULT:
            result["startExpanded"] = True
        return result

    def generate(
        self,
        sections: Sequence[tuple[str, spy.ast.Node]],
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
  <script>SPyAstViz.restoreFromHash();</script>
</body>
</html>
"""
