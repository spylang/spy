from toyast import EXAMPLE, Module, Assign, If, Const, BinOp

NODE_W = 110
NODE_H = 28
X_INDENT = 40
ROW_H = 44
PAD = 20

svg_nodes = []  # (x, y, label)
svg_lines = []  # (x1, y1, x2, y2)


def label_of(node):
    if isinstance(node, Assign):
        return f'Assign: {node.target}'
    if isinstance(node, BinOp):
        return f'BinOp: {node.op}'
    if isinstance(node, Const):
        return f'Const: {node.value}'
    return type(node).__name__


def children_of(node):
    if isinstance(node, Module):
        return node.body
    if isinstance(node, Assign):
        return [node.value]
    if isinstance(node, If):
        return [node.test] + node.then_body + node.else_body
    if isinstance(node, BinOp):
        return [node.left, node.right]
    return []


def visit(node, x, y):
    """Append node to svg_nodes, draw connectors to children, return next y."""
    svg_nodes.append((x, y, label_of(node)))
    ny = y + ROW_H

    children = children_of(node)

    if not children:
        return ny

    child_x = x + X_INDENT
    vx = child_x - X_INDENT // 2  # x of vertical connector

    child_mids = []
    for child in children:
        child_mids.append(ny + NODE_H // 2)
        ny = visit(child, child_x, ny)

    # vertical line from parent bottom down to last child mid-y
    svg_lines.append((vx, y + NODE_H, vx, child_mids[-1]))
    # horizontal branches to each child
    for mid_y in child_mids:
        svg_lines.append((vx, mid_y, child_x, mid_y))

    return ny


visit(EXAMPLE, PAD, PAD)

W = max(x + NODE_W for x, y, _ in svg_nodes) + PAD
H = max(y + NODE_H for x, y, _ in svg_nodes) + PAD

lines_svg = '\n'.join(
    f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"'
    f' stroke="#94a3b8" stroke-width="1.5"/>'
    for x1, y1, x2, y2 in svg_lines
)

nodes_svg = []
for x, y, label in svg_nodes:
    cx = x + NODE_W // 2
    cy = y + NODE_H // 2 + 5
    nodes_svg.append(
        f'  <rect x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}"'
        f' rx="4" fill="#dbeafe" stroke="#3b82f6" stroke-width="1.5"/>\n'
        f'  <text x="{cx}" y="{cy}" text-anchor="middle"'
        f' font-family="monospace" font-size="13" fill="#1e3a5f">{label}</text>'
    )
nodes_svg = '\n'.join(nodes_svg)

svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">\n{lines_svg}\n{nodes_svg}\n</svg>'

html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>AST Visualizer</title>
</head>
<body style="background:#f8fafc; padding:20px; font-family:sans-serif;">
  <h2>AST: EXAMPLE</h2>
  {svg}
</body>
</html>
"""

with open('/tmp/mermaid/output.html', 'w') as f:
    f.write(html)

print("Written output.html")
