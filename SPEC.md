# AST Visualizer — Specification

## Overview

An interactive, browser-based SVG visualizer for Abstract Syntax Trees. The visualizer
renders a tree of typed nodes as an HTML file containing a single `<svg>` element driven
entirely by JavaScript. All layout and rendering happens client-side; the server/build
step only serializes the AST to JSON and embeds it in the page.

Nodes can be collapsed and expanded by clicking. Collapsed nodes show their source
representation inline. All layout changes animate smoothly.

---

## 1. Input Contract

The library consumer must provide, for each node type in their AST:

### 1.1 Node classification

Every node belongs to one of two **rendering classes**:

| Class | Description |
|-------|-------------|
| `stmt` | "Statement-like" — rendered in a **folder/tree-list layout** (vertical, indented) |
| `expr` | "Expression-like" — rendered in a **top-down tree layout** (parent centered above children) |

The classification is binary and exhaustive. A node is either `expr` or `stmt`; there is no
third class. `stmt` nodes may have `expr` children; `expr` nodes may only have `expr`
children. `stmt` nodes are never children of `expr` nodes.

### 1.2 JSON serialization

The AST is serialized to a plain JSON object tree. Each node object must have at minimum:

```json
{
  "type": "<NodeTypeName>",
  "src":  "<source string for this subtree>"
}
```

`src` is the source-code fragment that this node represents. It may be multi-line. It is
used both as the content of collapsed nodes and as the hover tooltip of expanded ones.

Additional fields carry child nodes or leaf data. Example:

```json
{
  "type": "BinOp",
  "src":  "1 + 2 * 3",
  "op":   "+",
  "left": { "type": "Const", "src": "1", "value": 1 },
  "right": { "type": "BinOp", "src": "2 * 3", "op": "*",
             "left":  { "type": "Const", "src": "2", "value": 2 },
             "right": { "type": "Const", "src": "3", "value": 3 } }
}
```

### 1.3 Per-node configuration (provided by the consumer)

The library requires the consumer to supply three functions:

```js
// Returns the display label for a node (single line, shown when expanded).
labelOf(node) → string

// Returns true if the node belongs to the expr rendering class.
isExpr(node) → boolean

// Returns the named children of a node as [{attr, node}, ...].
// attr is the attribute/field name (shown as edge label).
// Returns [] for leaf nodes.
// For stmt nodes: should not return expr children mixed with stmt children
//   in a way that would require stmt-inside-expr (unsupported).
childrenOf(node) → Array<{attr: string, node: object}>
```

`childrenOf` is the only source of structural information used by the layout engine.
It must reflect the current collapsed/expanded state if the consumer wants partial
subtrees; however, the visualizer manages collapse state internally and calls
`childrenOf` only on non-collapsed nodes.

---

## 2. Internal Node Preparation

Before the first render, the library performs a one-time traversal of the JSON tree to
assign a **stable integer ID** (`_id`) to every node object. IDs are assigned in
pre-order (depth-first, parent before children).

```
assignIds(node):
    node._id = nextId++
    for each child in childrenOf(node):
        assignIds(child)
```

IDs are used as keys in the `collapsed` Set and in all DOM element Maps. They must never
change across renders.

---

## 3. Collapse State

A `Set<id>` called `collapsed` tracks which nodes are currently collapsed.

**Initial state:** all collapsible nodes start collapsed. A node is collapsible if
`childrenOf(node).length > 0` (for `stmt` nodes) or if it is an `expr` node with
children (e.g. `BinOp` but not `Const`).

Clicking a collapsible node toggles its ID in `collapsed`, then triggers a full re-layout
and re-render.

---

## 4. Layout

Layout is computed fresh on every render into two flat arrays:

- `svgNodes`: list of node boxes to draw
- `svgLines`: list of connector segments to draw

Both arrays are re-computed from scratch each render; the DOM is then reconciled against
them (see Section 6).

### 4.1 Node box size

```
nodeSize(node) → {w, h}
```

- If the node is **not collapsed** (or is a leaf): `w = NODE_W`, `h = NODE_H`
- If the node **is collapsed** (and has children): size is computed from `src`:
  ```
  lines = src.split('\n')
  w = max(NODE_W,  max_line_length × CHAR_W + 2 × SRC_PAD_X)
  h = line_count  × LINE_H + 2 × SRC_PAD_Y
  ```

The variable-size collapsed box is what allows `src` to be shown inline without
truncation. Surrounding nodes reposition to accommodate it.

### 4.2 Stmt (folder-view) layout

`visit(node, x, y)` places `node` at `(x, y)` and returns the next available `y`.

```
visit(node, x, y):
    {w: nw, h: nh} = nodeSize(node)
    emit svgNode at (x, y, nw, nh)
    ny = y + nh + ROW_GAP

    if node is collapsed or has no children:
        return ny

    childX = x + X_INDENT
    vx     = childX - X_INDENT / 2        # x of vertical trunk line

    connectors = []
    for {attr, node: child} in childrenOf(node):
        childNh = nodeSize(child).h
        midY    = ny + childNh / 2         # y of horizontal branch line

        if isExpr(child):
            totalW   = measureExpr(child)
            nodeLeftX = childX + (totalW - nodeSize(child).w) / 2
            connectors.append({x: nodeLeftX, y: midY, attr, childId: child._id})
            ny = placeExpr(child, childX, ny) + ROW_GAP
        else:
            connectors.append({x: childX, y: midY, attr, childId: child._id})
            ny = visit(child, childX, ny)

    # vertical trunk: from parent bottom to last child's midY
    emit line (vx, y+nh) → (vx, connectors.last.y)   id="v-{node._id}"

    # horizontal branches: one per child
    for {x: tx, y: ty, attr, childId} in connectors:
        emit line (vx, ty) → (tx, ty)   label=attr   id="h-{node._id}-{childId}"

    return ny
```

### 4.3 Expr (top-down tree) layout

#### measureExpr

```
measureExpr(node):
    if collapsed or not a binary node: return nodeSize(node).w
    return measureExpr(left) + EXPR_H_GAP + measureExpr(right)
```

This computes the total horizontal space needed by the subtree, accounting for collapse.

#### placeExpr

```
placeExpr(node, leftX, y):
    totalW = measureExpr(node)
    {w: nw, h: nh} = nodeSize(node)
    nodeX = leftX + (totalW - nw) / 2     # center node over its subtree
    emit svgNode at (nodeX, y, nw, nh)

    if node has no children or is collapsed:
        return y + nh

    childY  = y + nh + EXPR_V_GAP
    midY    = y + nh + EXPR_V_GAP / 2     # y of the horizontal bar

    leftW  = measureExpr(left);   lnw = nodeSize(left).w
    rightW = measureExpr(right);  rnw = nodeSize(right).w

    lChildCx = leftX + leftW/2
    rChildCx = leftX + leftW + EXPR_H_GAP + rightW/2
    parentCx = nodeX + nw/2

    # 4 orthogonal connector segments:
    emit line (parentCx, y+nh) → (parentCx, midY)    id="evs-{node._id}"   # stem
    emit line (lChildCx, midY) → (parentCx,  midY)   id="ehl-{node._id}"   label="left"
    emit line (parentCx, midY) → (rChildCx,  midY)   id="ehr-{node._id}"   label="right"
    emit line (lChildCx, midY) → (lChildCx, childY)  id="el-{node._id}-{left._id}"
    emit line (rChildCx, midY) → (rChildCx, childY)  id="er-{node._id}-{right._id}"

    lb = placeExpr(left,  leftX,                       childY)
    rb = placeExpr(right, leftX + leftW + EXPR_H_GAP,  childY)
    return max(lb, rb)
```

Note: the horizontal bar is split into two labeled halves so that the "left"/"right"
labels are centered above each side of the bar.

---

## 5. Visual Design

### 5.1 Dimensions and constants

| Constant | Value | Meaning |
|----------|-------|---------|
| `NODE_W` | 110 | Default node box width (px) |
| `NODE_H` | 28 | Default node box height (px) |
| `X_INDENT` | 120 | Horizontal indent per level in folder view (px). Half of this is the horizontal connector length. |
| `ROW_GAP` | 16 | Vertical gap between rows in folder view (px) |
| `EXPR_H_GAP` | 16 | Horizontal gap between sibling expr subtrees (px) |
| `EXPR_V_GAP` | 30 | Vertical gap between parent and children in expr tree (px). The horizontal bar sits at half this distance. |
| `CHAR_W` | 7.8 | Approximate width per monospace character at font-size 13 (px) |
| `LINE_H` | 18 | Line height for multi-line src text (px) |
| `SRC_PAD_X` | 10 | Horizontal padding inside src text boxes (px) |
| `SRC_PAD_Y` | 8 | Vertical padding inside src text boxes (px) |

### 5.2 Node colors

Nodes have two visual axes: **class** (stmt / expr) × **state** (expanded / collapsed).

| | Expanded | Collapsed |
|-|----------|-----------|
| **stmt** | fill `#dbeafe`, stroke `#3b82f6` (blue) | fill `#e0e7ff`, stroke `#6366f1` (indigo) |
| **expr** | fill `#fef9c3`, stroke `#ca8a04` (amber) | fill `#fef3c7`, stroke `#d97706` (dark amber) |

### 5.3 Node text

**Expanded node:** single centered line showing `labelOf(node)`, prefixed with `▼` if
the node has children (clickable). Font: monospace 13px, color `#1e3a5f`.

**Collapsed node:** multi-line `src` text, left-aligned with `SRC_PAD_X`/`SRC_PAD_Y`
padding. Font: monospace 13px, color `#312e81` (stmt) or `#78350f` (expr).
No collapse indicator is needed because the src content serves as visual confirmation.

### 5.4 Connector lines

All lines: stroke `#94a3b8`, stroke-width 1.5.

Edge label text: sans-serif 10px, color `#64748b`, centered at the midpoint of the
segment plus an optional `labelDx` x-offset (used for labels on vertical segments).

### 5.5 Tooltip

When the cursor hovers over an **expanded** collapsible node for more than **600 ms**, a
tooltip appears directly below the node showing the full `src` text. The tooltip uses the
same styling as a collapsed node of the same class (same fill/stroke/font/colors). It has
a subtle drop-shadow (`drop-shadow(0 2px 4px rgba(0,0,0,.15))`). It disappears
immediately on `mouseout` or if the timer is cancelled (cursor left before 600 ms).

---

## 6. DOM Reconciliation and Animation

The library maintains two persistent Maps keyed by stable IDs:

- `nodeElements: Map<id, HTMLElement>` — one `<g>` per node
- `lineElements: Map<id, {line, text, labelDx}>` — one `<line>` (+ optional `<text>`) per segment

The SVG contains three child `<g>` layers in order: `linesGroup`, `nodesGroup`,
`tooltipGroup`. The tooltip group is always on top.

### 6.1 Node animation

Each node `<g>` is permanently in the DOM (until the node disappears). It is positioned
via CSS `transform: translate(Xpx, Ypx)`. All inner elements (`<rect>`, `<text>`) use
coordinates relative to the group origin (x=0, y=0).

On re-render:
- **Existing node, same position**: update content (colors, text) instantly; no CSS change.
- **Existing node, new position**: set `transition: transform 300ms ease`, update transform → browser animates.
- **New node** (just became visible): create `<g>`, set `opacity: 0`, append to DOM, then
  double-`requestAnimationFrame` to set `opacity: 1` (triggers 300ms fade-in).
- **Removed node** (became hidden): set `opacity: 0` with `transition: opacity 300ms ease`,
  remove from DOM after 300ms.

The double-rAF is necessary to ensure the browser has painted the initial `opacity: 0`
state before the transition to `opacity: 1` begins.

Content (rect size, colors, label text) is rebuilt synchronously on every render by
clearing and re-populating the `<g>` children. There is no animation on content changes —
only position and opacity animate.

### 6.2 Line animation

Each line segment has a stable string ID (see Section 4). On re-render:

- **Unchanged line**: `parseFloat(getAttribute(...))` matches target → no action.
- **Moved line**: animate from current DOM attribute values to new values using a manual
  `requestAnimationFrame` loop with ease-in-out interpolation over `ANIM_MS = 300ms`.
  The label `<text>` tracks the animated midpoint of the segment throughout.
- **New line**: create element, `opacity: 0`, double-rAF → `opacity: 1`.
- **Removed line**: `opacity: 0` with CSS transition, remove after 300ms.

Because attribute values are read from the DOM at the start of each animation, rapid
re-triggers (click during animation) start correctly from the current mid-animation
position rather than the previous target.

### 6.3 First render

A `firstRender` boolean suppresses all animations on the initial render. Everything
appears instantly.

---

## 7. Stable Line IDs

| ID pattern | Segment |
|------------|---------|
| `v-{parentId}` | Vertical trunk in folder-view (parent bottom → last child midY) |
| `h-{parentId}-{childId}` | Horizontal branch in folder-view |
| `evs-{nodeId}` | Vertical stem in expr tree (parent bottom → horizontal bar) |
| `ehl-{nodeId}` | Left half of horizontal bar in expr tree (carries "left" label) |
| `ehr-{nodeId}` | Right half of horizontal bar in expr tree (carries "right" label) |
| `el-{nodeId}-{leftId}` | Left drop in expr tree (bar → left child top) |
| `er-{nodeId}-{rightId}` | Right drop in expr tree (bar → right child top) |

---

## 8. Library Interface (proposed)

A generic implementation should expose:

```js
ASTVisualizer.init(svgElement, {
    // Required
    data:        object,          // root node (JSON-serialized AST)
    labelOf:     node => string,
    isExpr:      node => bool,
    childrenOf:  node => [{attr, node}],

    // Optional overrides
    NODE_W:      number,          // default 110
    NODE_H:      number,          // default 28
    X_INDENT:    number,          // default 120
    EXPR_H_GAP:  number,          // default 16
    EXPR_V_GAP:  number,          // default 30
    ANIM_MS:     number,          // default 300
    TOOLTIP_MS:  number,          // default 600
    colors: {
        stmt: { expanded, collapsed },   // {fill, stroke}
        expr: { expanded, collapsed },
    },
})
```

The library manages all internal state (IDs, `collapsed` Set, DOM Maps) and re-renders
automatically when a node is clicked.

---

## 9. Build / Deployment

The reference implementation generates a **self-contained HTML file**:

1. The AST is serialized to JSON by a Python script (`gen.py`) using a recursive
   `to_dict(node)` function that traverses the AST and emits `{type, src, ...children}`.
2. The JSON is embedded in a `<script>` tag as a JS variable (`const astData = ...`).
3. The visualizer JS is inlined in the same `<script>` tag (no external dependencies).
4. The output is a single `.html` file with no external resources.

This approach makes the output trivially shareable and viewable offline.
