# spyast.js — AST Visualizer

Interactive, browser-based SVG visualizer for Abstract Syntax Trees. Nodes can
be expanded and collapsed by clicking. Layout and state are managed client-side;
the only server-side step is serializing the AST to JSON.

---

## Installation

### CDN (production)

```html
<script src="https://cdn.jsdelivr.net/gh/spy-lang/spy/spyast.js"></script>
```

### Local development

Download `spyast.js` alongside your HTML file and open it in a browser directly
(`file://` works — no server required).

---

## Basic usage

```html
<svg id="diagram"></svg>
<script src="spyast.js"></script>
<script>
  SPyAstViz.render(document.getElementById('diagram'), astData);
</script>
```

`SPyAstViz.render(svgEl, astData)` is the only public API. Each call creates an
independent instance with its own state (collapsed set, DOM maps, etc.), so
multiple diagrams on the same page work without interference.

The SVG element's `width` and `height` are set automatically on every render.

---

## JSON node schema

Every node in `astData` is a plain JSON object. The fields below are read by the
library; any extra fields are ignored.

### Required fields

| Field | Type | Description |
|-------|------|-------------|
| `label` | `string` | Text displayed inside the node when **expanded**. |
| `expr` | `boolean` | Layout mode. `true` → top-down expression tree; `false` → indented folder view. |
| `children` | `array` | Named children: `[{ attr: string, node: object }, ...]`. Use `[]` for leaf nodes. |

### Optional fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `src` | `string` | `""` | Source-code fragment this node represents. Shown as the node body when **collapsed**, and as a tooltip (after 600 ms hover) when expanded. May be multi-line. |
| `shape` | `string` | `"stmt"` | Visual outline shape. See [Shapes](#shapes). |
| `color` | `string` | `"gray"` | Fill/stroke color palette entry. See [Colors](#colors). |
| `startExpanded` | `boolean` | `false` | If `true`, the node starts expanded instead of collapsed. |

### Minimal example

```json
{
  "label": "Module",
  "expr": false,
  "src": "x = 1\ny = 2",
  "shape": "stmt",
  "color": "blue",
  "startExpanded": true,
  "children": [
    {
      "attr": "body[0]",
      "node": {
        "label": "Assign",
        "expr": false,
        "src": "x = 1",
        "shape": "stmt",
        "color": "blue",
        "children": []
      }
    }
  ]
}
```

---

## Shapes

The `shape` field controls the outline drawn around the node box.

| Value | Appearance | Intended use |
|-------|-----------|--------------|
| `"stmt"` | Rounded rectangle (rx=4) | Statement / container nodes |
| `"expr"` | Pill / stadium (rx = height/2) | Expression / value nodes |
| `"leaf"` | Hexagon (pointed left and right) | Terminal / identifier nodes (strings rendered as tree nodes) |

Any unknown value falls back to `"stmt"` behaviour (rounded rectangle).

---

## Colors

The `color` field selects a fill/stroke pair from the built-in palette. Colors
have two shades: one for the expanded state and one (slightly deeper) for the
collapsed state.

| Value | Expanded fill | Collapsed fill | Stroke |
|-------|--------------|----------------|--------|
| `"blue"` | `#dbeafe` | `#e0e7ff` | `#3b82f6` / `#6366f1` |
| `"amber"` | `#fef9c3` | `#fef3c7` | `#ca8a04` / `#d97706` |
| `"emerald"` | `#d1fae5` | `#a7f3d0` | `#059669` / `#047857` |
| `"red"` | `#fee2e2` | `#fecaca` | `#ef4444` / `#dc2626` |
| `"purple"` | `#ede9fe` | `#ddd6fe` | `#7c3aed` / `#6d28d9` |
| `"gray"` | `#f1f5f9` | `#e2e8f0` | `#94a3b8` / `#64748b` |

Any unknown value falls back to `"gray"`.

---

## Layout

### Folder view (`expr: false`)

Stmt nodes are laid out like a file-explorer tree: vertically stacked,
indented one level per depth. Children are connected by an L-shaped connector
(vertical trunk + horizontal branch), with the `attr` name labelling each
branch.

When an `expr` child appears inside a folder-view node, it is placed inline
using the expression tree layout below.

### Expression tree (`expr: true`)

Expr nodes are laid out as a top-down binary tree: the parent is centred
above its two children, connected by orthogonal lines (vertical stem →
horizontal bar → vertical drops). The `attr` names of the first two children
label the left and right halves of the horizontal bar.

Only the first two children are used for the tree layout. Nodes with zero
children render as leaves (no connectors below them).

---

## Collapse behaviour

- All nodes with children start **collapsed** by default, showing their `src`
  text as the node body.
- Set `startExpanded: true` on any node to have it begin expanded.
- Clicking a node toggles its collapsed state and re-renders with animation.
- A **▶** chevron (collapsed) or **▼** chevron (expanded) on the left of the
  node indicates it is interactive.
- Leaf nodes (empty `children`) are never collapsible and show no chevron.

---

## URL state / permalinks

The current collapsed/expanded state is encoded in the URL hash as a
comma-separated list of collapsed node IDs:

```
output.html#1,3,7,12
```

The hash is updated silently (via `history.replaceState`) on every click, so
the address bar always contains a shareable permalink to the exact current view.
On page load, if a hash is present it is restored; otherwise the default
collapse state (all nodes collapsed except those with `startExpanded: true`)
is used.

---

## Animation

All layout changes animate over 300 ms:

- **Nodes** slide to their new position via CSS `transform` transitions.
- **Connector lines** interpolate their endpoints via a `requestAnimationFrame`
  loop with ease-in-out easing.
- New nodes and lines fade in; removed ones fade out.
- Tooltips are suppressed during animation and re-enabled once it completes.

The first render is always instant (no animation).

---

## Reference implementation (Python)

`toyast.py` and `gen.py` are a reference implementation showing how to connect
a Python AST to `spyast.js`. They are not part of the library itself.

**`toyast.py`** defines a small toy language AST (nodes like `Module`, `Assign`,
`If`, `BinOp`, `FuncDef`, etc.) and an `EXAMPLE` program that exercises all
node types. It also contains `attach_src`, which computes a source-code string
for every node by reconstructing it from the tree. This is only needed because
the AST is fabricated — in a real compiler the `src` field would be populated
from the actual source file on disk using the parser's source spans.

**`gen.py`** shows how to convert that AST into the JSON schema expected by
`spyast.js` and produce a self-contained HTML file. The key function is
`to_dict`, which walks the dataclass fields automatically (via
`dataclasses.fields()`) and decides for each field whether it becomes a child
node, a list of child nodes, or just contributes to the label. Three small
config dicts at the top of the file encode all the display decisions specific
to this AST (which field to append to the label, which string fields to render
as leaf nodes, which nodes start expanded). These are the only things that need
to change when adapting `gen.py` to a different AST.

---

## Constants (internal defaults)

These are compiled into the library and are not currently runtime-configurable.

| Constant | Value | Meaning |
|----------|-------|---------|
| `NODE_H` | 28 px | Height of an expanded node |
| `X_INDENT` | 120 px | Horizontal indent per folder-view level |
| `ROW_GAP` | 16 px | Vertical gap between rows in folder view |
| `EXPR_H_GAP` | 16 px | Horizontal gap between sibling expr subtrees |
| `EXPR_V_GAP` | 30 px | Vertical gap between parent and children in expr tree |
| `ANIM_MS` | 300 ms | Animation duration |
| `CHAR_W` | 7.8 px | Approximate width per monospace character (font-size 13) |
| `LINE_H` | 18 px | Line height for multi-line `src` text |
| `ARROW_W` | 26 px | Space reserved on the left for the collapse chevron |
