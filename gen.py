import json
from toyast import EXAMPLE, Module, Assign, If, Const, BinOp


def to_dict(node):
    if isinstance(node, Module):
        return {'type': 'Module', 'src': node.src, 'body': [to_dict(s) for s in node.body]}
    if isinstance(node, Assign):
        return {'type': 'Assign', 'src': node.src, 'target': node.target, 'value': to_dict(node.value)}
    if isinstance(node, If):
        return {'type': 'If', 'src': node.src,
                'test': to_dict(node.test),
                'then_body': [to_dict(s) for s in node.then_body],
                'else_body': [to_dict(s) for s in node.else_body]}
    if isinstance(node, BinOp):
        return {'type': 'BinOp', 'src': node.src, 'op': node.op,
                'left': to_dict(node.left), 'right': to_dict(node.right)}
    if isinstance(node, Const):
        return {'type': 'Const', 'src': node.src, 'value': node.value}
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

const NODE_W = 110, NODE_H = 28;
const X_INDENT = 40, ROW_GAP = 16;
const EXPR_H_GAP = 16, EXPR_V_GAP = 30, PAD = 20;
const CHAR_W = 7.8, LINE_H = 18, SRC_PAD_X = 10, SRC_PAD_Y = 8;

// --- assign stable IDs once ---
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
function isExpr(node)  {{ return node.type === 'BinOp' || node.type === 'Const'; }}
function canCollapse(node) {{ return node.type === 'BinOp' || childrenOf(node).length > 0; }}

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

// Returns the dimensions of the node box itself (not the whole subtree).
// Collapsed nodes with children expand to show their src.
function nodeSize(node) {{
  if (!collapsed.has(node._id) || !canCollapse(node))
    return {{w: NODE_W, h: NODE_H}};
  const lines = (node.src || '').split('\\n');
  const maxLen = Math.max(...lines.map(l => l.length));
  return {{
    w: Math.max(NODE_W, Math.ceil(maxLen * CHAR_W) + 2 * SRC_PAD_X),
    h: lines.length * LINE_H + 2 * SRC_PAD_Y,
  }};
}}

// --- expr layout ---
function measureExpr(node) {{
  if (collapsed.has(node._id) || node.type !== 'BinOp') return nodeSize(node).w;
  return measureExpr(node.left) + EXPR_H_GAP + measureExpr(node.right);
}}

function placeExpr(node, leftX, y, svgNodes, svgLines) {{
  const totalW = measureExpr(node);
  const {{w: nw, h: nh}} = nodeSize(node);
  const nodeX = leftX + (totalW - nw) / 2;
  const isCollapsed = collapsed.has(node._id);
  svgNodes.push({{x: nodeX, y, nw, nh, label: labelOf(node), src: node.src,
                  id: node._id, hasChildren: node.type === 'BinOp', isCollapsed}});

  if (node.type === 'BinOp' && !isCollapsed) {{
    const childY = y + nh + EXPR_V_GAP;
    const leftW  = measureExpr(node.left);
    const rightW = measureExpr(node.right);
    const {{w: lnw}} = nodeSize(node.left);
    const {{w: rnw}} = nodeSize(node.right);
    const leftChildX  = leftX + (leftW - lnw) / 2;
    const rightChildX = leftX + leftW + EXPR_H_GAP + (rightW - rnw) / 2;
    const parentCx = nodeX + nw / 2;
    svgLines.push({{x1: parentCx, y1: y + nh, x2: leftChildX  + lnw / 2, y2: childY}});
    svgLines.push({{x1: parentCx, y1: y + nh, x2: rightChildX + rnw / 2, y2: childY}});
    const lb = placeExpr(node.left,  leftX,                      childY, svgNodes, svgLines);
    const rb = placeExpr(node.right, leftX + leftW + EXPR_H_GAP, childY, svgNodes, svgLines);
    return Math.max(lb, rb);
  }}
  return y + nh;
}}

// --- stmt folder-view layout ---
function visit(node, x, y, svgNodes, svgLines) {{
  const {{w: nw, h: nh}} = nodeSize(node);
  const children = childrenOf(node);
  const hasChildren = children.length > 0;
  const isCollapsed = collapsed.has(node._id);
  svgNodes.push({{x, y, nw, nh, label: labelOf(node), src: node.src,
                  id: node._id, hasChildren, isCollapsed}});
  let ny = y + nh + ROW_GAP;

  if (!hasChildren || isCollapsed) return ny;

  const childX = x + X_INDENT;
  const vx = childX - X_INDENT / 2;

  const connectors = [];
  for (const child of children) {{
    const childNh = nodeSize(child).h;
    const midY = ny + childNh / 2;
    if (isExpr(child)) {{
      const totalW = measureExpr(child);
      const {{w: cnw}} = nodeSize(child);
      connectors.push({{x: childX + (totalW - cnw) / 2, y: midY}});
      ny = placeExpr(child, childX, ny, svgNodes, svgLines) + ROW_GAP;
    }} else {{
      connectors.push({{x: childX, y: midY}});
      ny = visit(child, childX, ny, svgNodes, svgLines);
    }}
  }}

  svgLines.push({{x1: vx, y1: y + nh, x2: vx, y2: connectors[connectors.length - 1].y}});
  for (const {{x: tx, y: ty}} of connectors)
    svgLines.push({{x1: vx, y1: ty, x2: tx, y2: ty}});

  return ny;
}}

// --- render ---
function render() {{
  const svgNodes = [], svgLines = [];
  visit(astData, PAD, PAD, svgNodes, svgLines);

  const W = Math.max(...svgNodes.map(n => n.x + n.nw)) + PAD;
  const H = Math.max(...svgNodes.map(n => n.y + n.nh)) + PAD;

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

  for (const {{x, y, nw, nh, label, src, id, hasChildren, isCollapsed}} of svgNodes) {{
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
    rect.setAttribute('width', nw); rect.setAttribute('height', nh);
    rect.setAttribute('rx', 4);
    rect.setAttribute('fill',   isCollapsed ? '#e0e7ff' : '#dbeafe');
    rect.setAttribute('stroke', isCollapsed ? '#6366f1' : '#3b82f6');
    rect.setAttribute('stroke-width', '1.5');
    g.appendChild(rect);

    if (isCollapsed && src) {{
      // multi-line src display
      const text = document.createElementNS(NS, 'text');
      text.setAttribute('x', x + SRC_PAD_X);
      text.setAttribute('y', y + SRC_PAD_Y + 13);
      text.setAttribute('font-family', 'monospace');
      text.setAttribute('font-size', '13');
      text.setAttribute('fill', '#312e81');
      text.setAttribute('pointer-events', 'none');
      src.split('\\n').forEach((line, i) => {{
        const tspan = document.createElementNS(NS, 'tspan');
        tspan.setAttribute('x', x + SRC_PAD_X);
        if (i > 0) tspan.setAttribute('dy', LINE_H);
        tspan.textContent = line;
        text.appendChild(tspan);
      }});
      g.appendChild(text);
    }} else {{
      const text = document.createElementNS(NS, 'text');
      text.setAttribute('x', x + nw / 2);
      text.setAttribute('y', y + nh / 2 + 5);
      text.setAttribute('text-anchor', 'middle');
      text.setAttribute('font-family', 'monospace');
      text.setAttribute('font-size', '13');
      text.setAttribute('fill', '#1e3a5f');
      text.setAttribute('pointer-events', 'none');
      text.textContent = (hasChildren ? (isCollapsed ? '▶ ' : '▼ ') : '') + label;
      g.appendChild(text);
    }}

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
