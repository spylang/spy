import json
from toyast import EXAMPLE, Module, Assign, If, Const, BinOp


def to_dict(node):
    if isinstance(node, Module):
        return {'type': 'Module', 'body': [to_dict(s) for s in node.body]}
    if isinstance(node, Assign):
        return {'type': 'Assign', 'target': node.target, 'value': to_dict(node.value)}
    if isinstance(node, If):
        return {'type': 'If',
                'test': to_dict(node.test),
                'then_body': [to_dict(s) for s in node.then_body],
                'else_body': [to_dict(s) for s in node.else_body]}
    if isinstance(node, BinOp):
        return {'type': 'BinOp', 'op': node.op,
                'left': to_dict(node.left), 'right': to_dict(node.right)}
    if isinstance(node, Const):
        return {'type': 'Const', 'value': node.value}
    raise ValueError(f'Unknown node: {node}')


ast_json = json.dumps(to_dict(EXAMPLE), indent=2)

html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>AST Visualizer</title>
</head>
<body style="background:#f8fafc; padding:20px; font-family:sans-serif;">
  <h2>AST: EXAMPLE</h2>
  <svg id="diagram"></svg>
  <script>
const astData = {ast_json};

const NODE_W = 110, NODE_H = 28, X_INDENT = 40, ROW_H = 44, ROW_GAP = ROW_H - NODE_H;
const EXPR_H_GAP = 16, EXPR_V_GAP = 30, PAD = 20;

// --- assign stable IDs to every node once ---
let _idCounter = 0;
function assignIds(node) {{
  node._id = _idCounter++;
  if (node.type === 'Module')  node.body.forEach(assignIds);
  if (node.type === 'Assign')  assignIds(node.value);
  if (node.type === 'If')      {{ assignIds(node.test); node.then_body.forEach(assignIds); node.else_body.forEach(assignIds); }}
  if (node.type === 'BinOp')   {{ assignIds(node.left); assignIds(node.right); }}
}}
assignIds(astData);

const collapsed = new Set();

// --- helpers ---
function isExpr(node) {{ return node.type === 'BinOp' || node.type === 'Const'; }}

function labelOf(node) {{
  if (node.type === 'Assign') return `Assign: ${{node.target}}`;
  if (node.type === 'BinOp')  return `BinOp: ${{node.op}}`;
  if (node.type === 'Const')  return `Const: ${{node.value}}`;
  return node.type;
}}

function childrenOf(node) {{
  if (node.type === 'Module') return node.body;
  if (node.type === 'Assign') return [node.value];
  if (node.type === 'If')     return [node.test, ...node.then_body, ...node.else_body];
  return [];
}}

// --- expr layout ---
function measureExpr(node) {{
  if (collapsed.has(node._id) || node.type !== 'BinOp') return NODE_W;
  return measureExpr(node.left) + EXPR_H_GAP + measureExpr(node.right);
}}

function placeExpr(node, leftX, y, svgNodes, svgLines) {{
  const w = measureExpr(node);
  const nodeX = leftX + (w - NODE_W) / 2;
  const hasChildren = node.type === 'BinOp';
  svgNodes.push({{x: nodeX, y, label: labelOf(node), id: node._id, hasChildren}});

  if (hasChildren && !collapsed.has(node._id)) {{
    const childY = y + NODE_H + EXPR_V_GAP;
    const leftW  = measureExpr(node.left);
    const rightW = measureExpr(node.right);
    const leftChildX  = leftX + (leftW - NODE_W) / 2;
    const rightChildX = leftX + leftW + EXPR_H_GAP + (rightW - NODE_W) / 2;
    const parentCx = nodeX + NODE_W / 2;
    svgLines.push({{x1: parentCx, y1: y + NODE_H, x2: leftChildX  + NODE_W / 2, y2: childY}});
    svgLines.push({{x1: parentCx, y1: y + NODE_H, x2: rightChildX + NODE_W / 2, y2: childY}});
    const lb = placeExpr(node.left,  leftX,                       childY, svgNodes, svgLines);
    const rb = placeExpr(node.right, leftX + leftW + EXPR_H_GAP,  childY, svgNodes, svgLines);
    return Math.max(lb, rb);
  }}
  return y + NODE_H;
}}

// --- stmt folder-view layout ---
function visit(node, x, y, svgNodes, svgLines) {{
  const children = childrenOf(node);
  const hasChildren = children.length > 0;
  svgNodes.push({{x, y, label: labelOf(node), id: node._id, hasChildren}});
  let ny = y + ROW_H;

  if (!hasChildren || collapsed.has(node._id)) return ny;

  const childX = x + X_INDENT;
  const vx = childX - X_INDENT / 2;

  const connectors = [];
  for (const child of children) {{
    const midY = ny + NODE_H / 2;
    if (isExpr(child)) {{
      const nodeLeftX = childX + (measureExpr(child) - NODE_W) / 2;
      connectors.push({{x: nodeLeftX, y: midY}});
      ny = placeExpr(child, childX, ny, svgNodes, svgLines) + ROW_GAP;
    }} else {{
      connectors.push({{x: childX, y: midY}});
      ny = visit(child, childX, ny, svgNodes, svgLines);
    }}
  }}

  svgLines.push({{x1: vx, y1: y + NODE_H, x2: vx, y2: connectors[connectors.length - 1].y}});
  for (const {{x: tx, y: ty}} of connectors)
    svgLines.push({{x1: vx, y1: ty, x2: tx, y2: ty}});

  return ny;
}}

// --- render ---
function render() {{
  const svgNodes = [], svgLines = [];
  visit(astData, PAD, PAD, svgNodes, svgLines);

  const W = Math.max(...svgNodes.map(n => n.x + NODE_W)) + PAD;
  const H = Math.max(...svgNodes.map(n => n.y + NODE_H)) + PAD;

  const svg = document.getElementById('diagram');
  svg.setAttribute('width',  W);
  svg.setAttribute('height', H);
  svg.innerHTML = '';

  const NS = 'http://www.w3.org/2000/svg';

  for (const {{x1, y1, x2, y2}} of svgLines) {{
    const el = document.createElementNS(NS, 'line');
    el.setAttribute('x1', x1); el.setAttribute('y1', y1);
    el.setAttribute('x2', x2); el.setAttribute('y2', y2);
    el.setAttribute('stroke', '#94a3b8');
    el.setAttribute('stroke-width', '1.5');
    svg.appendChild(el);
  }}

  for (const {{x, y, label, id, hasChildren}} of svgNodes) {{
    const isCollapsed = collapsed.has(id);
    const g = document.createElementNS(NS, 'g');
    if (hasChildren) {{
      g.style.cursor = 'pointer';
      g.addEventListener('click', () => {{
        isCollapsed ? collapsed.delete(id) : collapsed.add(id);
        render();
      }});
    }}

    const rect = document.createElementNS(NS, 'rect');
    rect.setAttribute('x', x); rect.setAttribute('y', y);
    rect.setAttribute('width', NODE_W); rect.setAttribute('height', NODE_H);
    rect.setAttribute('rx', 4);
    rect.setAttribute('fill',   isCollapsed ? '#e0e7ff' : '#dbeafe');
    rect.setAttribute('stroke', isCollapsed ? '#6366f1' : '#3b82f6');
    rect.setAttribute('stroke-width', '1.5');

    const text = document.createElementNS(NS, 'text');
    text.setAttribute('x', x + NODE_W / 2);
    text.setAttribute('y', y + NODE_H / 2 + 5);
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('font-family', 'monospace');
    text.setAttribute('font-size', '13');
    text.setAttribute('fill', '#1e3a5f');
    text.setAttribute('pointer-events', 'none');
    text.textContent = (hasChildren ? (isCollapsed ? '▶ ' : '▼ ') : '') + label;

    g.appendChild(rect);
    g.appendChild(text);
    svg.appendChild(g);
  }}
}}

render();
  </script>
</body>
</html>
"""

with open('/tmp/mermaid/output.html', 'w') as f:
    f.write(html)

print("Written output.html")
