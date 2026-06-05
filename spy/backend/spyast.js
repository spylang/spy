// # WARNING: this file has written by autonomous coding assistans for the major part.
// spyast.js — standalone AST visualizer
// Usage: SPyAstViz.render(svgElement, astData)
//
// Each node in astData must have:
//   label        {string}  text shown when expanded
//   expr         {boolean} true → top-down tree layout; false → folder layout
//   children     {Array}   [{attr: string, node: object}, ...]; [] for leaves
//   src          {string}  source text shown when collapsed and in tooltip
//   startExpanded {boolean} optional; if true the node starts expanded (default: collapsed)
(function (global) {
  'use strict';

  const NODE_W = 110, NODE_H = 28;
  const X_INDENT = 120, ROW_GAP = 16;
  const EXPR_H_GAP = 16, EXPR_V_GAP = 30, PAD = 20;
  const CHAR_W = 7.8, LINE_H = 18, SRC_PAD_X = 10, SRC_PAD_Y = 8, ARROW_W = 26;
  const NS = 'http://www.w3.org/2000/svg';
  const ANIM_MS = 300;

  // Each entry has fill: [expanded, collapsed] and stroke: [expanded, collapsed].
  const PALETTE = {
    blue:    { fill: ['#b8d0e8', '#b8d0e8'], stroke: ['#87afd7', '#6a9ac4'] },
    amber:   { fill: ['#fef9c3', '#fef3c7'], stroke: ['#e0b840', '#e5c04a'] },
    emerald: { fill: ['#d1fae5', '#a7f3d0'], stroke: ['#6dd0a0', '#5cc090'] },
    red:     { fill: ['#e8c0c0', '#e8c0c0'], stroke: ['#d78787', '#c07070'] },
    default: { fill: ['#f5f5f5', '#ffffff'], stroke: ['#c0c0c0', '#c0c0c0'] },
  };

  // ---- page-level state ----
  const _instances = [];    // [{svgEl, astData, sectionIdx, headerEl, render, collapsed, ...}]
  let _focusSection = -1;   // -1 = show all
  let _focusNodeId = -1;
  let _contextMenu = null;
  let _showAllBanner = null;
  let _hideLeaves = false;

  function _removeContextMenu() {
    if (_contextMenu) { _contextMenu.remove(); _contextMenu = null; }
  }

  function _buildContextMenu(x, y, items) {
    _removeContextMenu();
    const menu = document.createElement('div');
    menu.id = 'spyast-context-menu';
    menu.style.cssText = `position:fixed;left:${x}px;top:${y}px;background:#fff;border:1px solid #ccc;border-radius:4px;box-shadow:0 2px 8px rgba(0,0,0,.18);z-index:10000;font-family:sans-serif;font-size:13px;padding:2px 0;min-width:160px;`;
    for (const { label, action } of items) {
      const item = document.createElement('div');
      item.textContent = label;
      item.style.cssText = 'padding:5px 16px;cursor:pointer;';
      item.addEventListener('mouseenter', () => { item.style.background = '#e8f0fe'; });
      item.addEventListener('mouseleave', () => { item.style.background = ''; });
      item.addEventListener('click', (e) => { e.stopPropagation(); _removeContextMenu(); action(); });
      menu.appendChild(item);
    }
    document.body.appendChild(menu);
    _contextMenu = menu;
  }

  function _findNode(node, id) {
    if (node._id === id) return node;
    for (const { node: child } of (node.children || [])) {
      const found = _findNode(child, id);
      if (found) return found;
    }
    return null;
  }

  function _focusOnNode(sectionIdx, nodeId) {
    _focusSection = sectionIdx;
    _focusNodeId = nodeId;
    _applyFocus();
    _writePageHash();
  }

  function _showAll() {
    _focusSection = -1;
    _focusNodeId = -1;
    _applyFocus();
    _writePageHash();
  }

  function _toggleLeaves() {
    _hideLeaves = !_hideLeaves;
    for (const inst of _instances) {
      inst.render();
    }
    _writePageHash();
  }

  function _copySVG(sectionIdx, nodeId) {
    const svg = _instances[sectionIdx].exportSubtreeSVG(nodeId);
    if (!svg) return;
    const blob = new Blob([svg], { type: 'image/svg+xml' });
    navigator.clipboard.write([new ClipboardItem({ 'image/svg+xml': blob })]).then(
      () => _showToast('SVG copied to clipboard'),
      () => {
        // Fallback: copy as text
        navigator.clipboard.writeText(svg).then(
          () => _showToast('SVG copied to clipboard (as text)'),
          () => _showToast('Failed to copy — try "Save SVG as file"')
        );
      }
    );
  }

  function _saveSVG(sectionIdx, nodeId, label) {
    const svg = _instances[sectionIdx].exportSubtreeSVG(nodeId);
    if (!svg) return;
    const name = (label || 'node').replace(/[^a-zA-Z0-9_.-]/g, '_') + '.svg';
    const blob = new Blob([svg], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function _showToast(msg) {
    const t = document.createElement('div');
    t.textContent = msg;
    t.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#333;color:#fff;padding:8px 20px;border-radius:6px;font-family:sans-serif;font-size:13px;z-index:10001;opacity:0;transition:opacity .3s;';
    document.body.appendChild(t);
    requestAnimationFrame(() => { t.style.opacity = '1'; });
    setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 2000);
  }

  function _applyFocus() {
    if (_focusSection >= 0) {
      // hide all sections except the focused one
      for (let i = 0; i < _instances.length; i++) {
        const inst = _instances[i];
        const show = (i === _focusSection);
        inst.svgEl.style.display = show ? '' : 'none';
        if (inst.headerEl) inst.headerEl.style.display = 'none';
      }
      // re-render the focused section with subtree root
      const inst = _instances[_focusSection];
      const subtree = _findNode(inst.astData, _focusNodeId);
      if (subtree) {
        inst.renderWith(subtree);
      }
      _showBanner();
    } else {
      // show everything, re-render each section with full AST
      for (const inst of _instances) {
        inst.svgEl.style.display = '';
        if (inst.headerEl) inst.headerEl.style.display = '';
        inst.renderWith(inst.astData);
      }
      _hideBanner();
    }
  }

  function _showBanner() {
    if (!_showAllBanner) {
      const banner = document.createElement('div');
      banner.id = 'spyast-show-all-banner';
      banner.style.cssText = 'position:fixed;top:0;left:0;right:0;background:#1e3a5f;color:#fff;text-align:center;padding:6px 12px;font-family:sans-serif;font-size:13px;z-index:9999;display:flex;align-items:center;justify-content:center;gap:12px;';
      const text = document.createElement('span');
      text.textContent = 'Showing subtree only';
      const btn = document.createElement('button');
      btn.textContent = 'Show all';
      btn.style.cssText = 'background:#fff;color:#1e3a5f;border:none;border-radius:3px;padding:3px 12px;cursor:pointer;font-size:13px;';
      btn.addEventListener('click', _showAll);
      banner.appendChild(text);
      banner.appendChild(btn);
      document.body.insertBefore(banner, document.body.firstChild);
      _showAllBanner = banner;
    }
    _showAllBanner.style.display = '';
  }

  function _hideBanner() {
    if (_showAllBanner) _showAllBanner.style.display = 'none';
  }

  // ---- page-level hash ----
  // Format: "s<sectionIdx>:<collapsedIds>;...;focus:<sectionIdx>:<nodeId>"
  // Simplified: we keep the old single-section format for backward compat when
  // there's only one section and no focus. Otherwise use the new format.
  function _writePageHash() {
    const parts = [];
    for (let i = 0; i < _instances.length; i++) {
      const inst = _instances[i];
      const ids = [...inst.collapsed].sort((a, b) => a - b).join(',');
      parts.push(`s${i}:${ids}`);
    }
    if (_focusSection >= 0) {
      parts.push(`focus:${_focusSection}:${_focusNodeId}`);
    }
    if (_hideLeaves) {
      parts.push('noleaves');
    }
    history.replaceState(null, '', '#' + parts.join(';'));
  }

  function _readPageHash() {
    const hash = location.hash.slice(1);
    if (!hash) return false;

    // New format: sections separated by ';'
    if (hash.includes('s0:') || hash.includes('focus:')) {
      const segments = hash.split(';');
      for (const seg of segments) {
        if (seg === 'noleaves') {
          _hideLeaves = true;
        } else if (seg.startsWith('focus:')) {
          const fParts = seg.split(':');
          _focusSection = parseInt(fParts[1]);
          _focusNodeId = parseInt(fParts[2]);
        } else if (seg.startsWith('s')) {
          const colonIdx = seg.indexOf(':');
          const idx = parseInt(seg.slice(1, colonIdx));
          const idsStr = seg.slice(colonIdx + 1);
          if (idx >= 0 && idx < _instances.length) {
            _instances[idx].collapsed.clear();
            idsStr.split(',').filter(Boolean).forEach(s => _instances[idx].collapsed.add(Number(s)));
          }
        }
      }
      return true;
    }

    // Legacy format: just comma-separated IDs for the first instance
    if (_instances.length > 0) {
      _instances[0].collapsed.clear();
      hash.split(',').filter(Boolean).forEach(s => _instances[0].collapsed.add(Number(s)));
      return true;
    }
    return false;
  }

  function init(svgEl, astData, initialCollapsed) {
    // ---- per-instance state ----
    const sectionIdx = _instances.length;
    let _idCounter = 0;
    const collapsed = new Set();
    const nodeElements = new Map();
    const lineElements = new Map();
    let linesGroup = null, nodesGroup = null, tooltipGroup = null;
    let firstRender = true;
    let _tooltipTimer = null;
    let _animating = false, _animatingTimer = null;
    let _currentRoot = astData;  // the root currently being rendered (may be a subtree)

    // Find the <h2> header immediately before this SVG
    let headerEl = null;
    let prev = svgEl.previousElementSibling;
    if (prev && prev.tagName === 'H2') headerEl = prev;

    // ---- generic node accessors ----
    function isExpr(node)      { return !!node.expr; }
    function labelOf(node)     { return node.label || node.type; }
    function childrenOf(node)  { return node.children || []; }
    function canCollapse(node) { return childrenOf(node).length > 0; }
    function visibleChildrenOf(node) {
      const ch = childrenOf(node);
      if (!_hideLeaves) return ch;
      return ch.filter(({ node: child }) => childrenOf(child).length > 0);
    }

    // ---- id assignment ----
    function assignIds(node) {
      node._id = _idCounter++;
      for (const { node: child } of childrenOf(node))
        assignIds(child);
    }

    // ---- collapsed init ----
    function initCollapsed(node) {
      if (canCollapse(node) && !node.startExpanded) collapsed.add(node._id);
      for (const { node: child } of childrenOf(node))
        initCollapsed(child);
    }

    // ---- layout ----
    function nodeSize(node) {
      if (!collapsed.has(node._id) || !canCollapse(node)) {
        const w = canCollapse(node)
          ? Math.max(NODE_W, ARROW_W + Math.ceil(labelOf(node).length * CHAR_W) + SRC_PAD_X)
          : Math.max(NODE_W, SRC_PAD_X + Math.ceil(labelOf(node).length * CHAR_W) + SRC_PAD_X);
        return { w, h: NODE_H };
      }
      const lines = (node.src || '').split('\n');
      const maxLen = Math.max(...lines.map(l => l.length));
      const leftPad = canCollapse(node) ? ARROW_W : SRC_PAD_X;
      return {
        w: Math.max(NODE_W, Math.ceil(maxLen * CHAR_W) + leftPad + SRC_PAD_X),
        h: lines.length * LINE_H + 2 * SRC_PAD_Y,
      };
    }

    // Expr layout: handles 0, 1, or 2 children.
    function measureExpr(node) {
      const ch = visibleChildrenOf(node);
      if (collapsed.has(node._id) || ch.length === 0) return nodeSize(node).w;
      if (ch.length === 1) return Math.max(nodeSize(node).w, measureExpr(ch[0].node));
      let total = 0;
      for (let i = 0; i < ch.length; i++) {
        if (i > 0) total += EXPR_H_GAP;
        total += measureExpr(ch[i].node);
      }
      return total;
    }

    function placeExpr(node, leftX, y, svgNodes, svgLines) {
      const ch = visibleChildrenOf(node);
      const totalW = measureExpr(node);
      const { w: nw, h: nh } = nodeSize(node);
      const nodeX = leftX + (totalW - nw) / 2;
      const isCollapsed = collapsed.has(node._id);
      svgNodes.push({ x: nodeX, y, nw, nh, label: labelOf(node), src: node.src, src_colors: node.src_colors,
                      id: node._id, hasChildren: ch.length > 0, isCollapsed, expr: true, shape: node.shape, color: node.color });

      if (ch.length === 1 && !isCollapsed) {
        const child = ch[0].node;
        const childY = y + nh + EXPR_V_GAP;
        const childW = measureExpr(child);
        const { w: cnw } = nodeSize(child);
        const childX = leftX + (totalW - cnw) / 2;
        const parentCx = nodeX + nw / 2;
        const childCx  = childX + cnw / 2;
        // straight vertical connector, no horizontal bar
        svgLines.push({ x1: parentCx, y1: y + nh, x2: childCx, y2: childY, id: `e1-${node._id}-${child._id}` });
        return placeExpr(child, leftX + (totalW - childW) / 2, childY, svgNodes, svgLines);
      }

      if (ch.length >= 2 && !isCollapsed) {
        const childY  = y + nh + EXPR_V_GAP;
        const parentCx = nodeX + nw / 2;
        const midY     = y + nh + EXPR_V_GAP / 2;

        // measure all children
        const childWidths = ch.map(c => measureExpr(c.node));
        const childNodeWidths = ch.map(c => nodeSize(c.node).w);

        // compute x positions for each child
        let cx = leftX;
        const childLeftXs = [];
        for (let i = 0; i < ch.length; i++) {
          childLeftXs.push(cx);
          cx += childWidths[i] + (i < ch.length - 1 ? EXPR_H_GAP : 0);
        }

        const childCenters = childLeftXs.map((lx, i) => lx + (childWidths[i] - childNodeWidths[i]) / 2 + childNodeWidths[i] / 2);

        // vertical stem from parent
        svgLines.push({ x1: parentCx, y1: y + nh, x2: parentCx, y2: midY, id: `evs-${node._id}` });

        // horizontal bar + vertical drops for each child
        for (let i = 0; i < ch.length; i++) {
          const ccx = childCenters[i];
          svgLines.push({ x1: parentCx, y1: midY, x2: ccx, y2: midY, label: ch[i].attr, id: `eh-${node._id}-${i}` });
          svgLines.push({ x1: ccx, y1: midY, x2: ccx, y2: childY, id: `ev-${node._id}-${ch[i].node._id}` });
        }

        // place children and track max bottom
        let maxBottom = y + nh;
        for (let i = 0; i < ch.length; i++) {
          const b = placeExpr(ch[i].node, childLeftXs[i], childY, svgNodes, svgLines);
          if (b > maxBottom) maxBottom = b;
        }
        return maxBottom;
      }
      return y + nh;
    }

    function visit(node, x, y, svgNodes, svgLines) {
      const { w: nw, h: nh } = nodeSize(node);
      const children = visibleChildrenOf(node);
      const hasChildren = childrenOf(node).length > 0;
      const isCollapsed = collapsed.has(node._id);
      svgNodes.push({ x, y, nw, nh, label: labelOf(node), src: node.src, src_colors: node.src_colors,
                      id: node._id, hasChildren, isCollapsed, expr: false, shape: node.shape, color: node.color });
      let ny = y + nh + ROW_GAP;

      if (!hasChildren || isCollapsed) return ny;

      const childX = x + X_INDENT;
      const vx = childX - X_INDENT / 2;

      const connectors = [];
      for (const { attr, node: child } of children) {
        const childNh = nodeSize(child).h;
        const midY = ny + childNh / 2;
        if (isExpr(child)) {
          const totalW = measureExpr(child);
          const { w: cnw } = nodeSize(child);
          connectors.push({ x: childX + (totalW - cnw) / 2, y: midY, attr, childId: child._id });
          ny = placeExpr(child, childX, ny, svgNodes, svgLines) + ROW_GAP;
        } else {
          connectors.push({ x: childX, y: midY, attr, childId: child._id });
          ny = visit(child, childX, ny, svgNodes, svgLines);
        }
      }

      svgLines.push({ x1: vx, y1: y + nh, x2: vx, y2: connectors[connectors.length - 1].y, id: `v-${node._id}` });
      for (const { x: tx, y: ty, attr, childId } of connectors)
        svgLines.push({ x1: vx, y1: ty, x2: tx, y2: ty, label: attr, id: `h-${node._id}-${childId}` });

      return ny;
    }

    // ---- tooltip ----
    function showTooltip(nd) {
      tooltipGroup.innerHTML = '';
      if (!nd.src || nd.isCollapsed || !nd.hasChildren) return;
      const lines = nd.src.split('\n');
      const maxLen = Math.max(...lines.map(l => l.length));
      const tw = Math.max(NODE_W, Math.ceil(maxLen * CHAR_W) + 2 * SRC_PAD_X);
      const th = lines.length * LINE_H + 2 * SRC_PAD_Y;
      const tx = nd.x, ty = nd.y + nd.nh + 6;

      const rect = document.createElementNS(NS, 'rect');
      rect.setAttribute('x', tx); rect.setAttribute('y', ty);
      rect.setAttribute('width', tw); rect.setAttribute('height', th);
      rect.setAttribute('rx', 4);
      const tc = nodeColors(nd.color, true);
      rect.setAttribute('fill',   tc.fill);
      rect.setAttribute('stroke', tc.stroke);
      rect.setAttribute('stroke-width', '1');
      rect.setAttribute('filter', 'drop-shadow(0 2px 4px rgba(0,0,0,.15))');
      tooltipGroup.appendChild(rect);

      const text = document.createElementNS(NS, 'text');
      text.setAttribute('x', tx + SRC_PAD_X);
      text.setAttribute('y', ty + SRC_PAD_Y + 13);
      text.setAttribute('font-family', 'monospace');
      text.setAttribute('font-size', '13');
      text.setAttribute('fill', { stmt: '#312e81', expr: '#78350f', leaf: '#065f46' }[nd.shape] || '#1e3a5f');
      text.setAttribute('pointer-events', 'none');
      lines.forEach((line, i) => {
        const tspan = document.createElementNS(NS, 'tspan');
        tspan.setAttribute('x', tx + SRC_PAD_X);
        if (i > 0) tspan.setAttribute('dy', LINE_H);
        tspan.textContent = line === '' ? '\u00A0' : line;
        text.appendChild(tspan);
      });
      tooltipGroup.appendChild(text);
    }

    function scheduleTooltip(nd) {
      if (_animating) return;
      _tooltipTimer = setTimeout(() => showTooltip(nd), 600);
    }
    function hideTooltip()       { clearTimeout(_tooltipTimer); tooltipGroup.innerHTML = ''; }

    // ---- animation ----
    function easeInOut(t) { return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t; }

    function animateLinePos(els, from, to) {
      const start = performance.now();
      function step(now) {
        const t  = easeInOut(Math.min((now - start) / ANIM_MS, 1));
        const x1 = from.x1 + (to.x1 - from.x1) * t;
        const y1 = from.y1 + (to.y1 - from.y1) * t;
        const x2 = from.x2 + (to.x2 - from.x2) * t;
        const y2 = from.y2 + (to.y2 - from.y2) * t;
        els.line.setAttribute('x1', x1); els.line.setAttribute('y1', y1);
        els.line.setAttribute('x2', x2); els.line.setAttribute('y2', y2);
        if (els.text) {
          els.text.setAttribute('x', (x1 + x2) / 2 + (els.labelDx || 0));
          els.text.setAttribute('y', (y1 + y2) / 2 - 3);
        }
        if (t < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    }

    // ---- DOM helpers ----
    function nodeColors(color, isCollapsed) {
      const c = PALETTE[color] || PALETTE.default;
      return { fill: c.fill[isCollapsed ? 1 : 0], stroke: c.stroke[isCollapsed ? 1 : 0] };
    }

    function buildNodeContent(g, nd) {
      while (g.firstChild) g.removeChild(g.firstChild);
      const { nw, nh, label, src, hasChildren, isCollapsed, shape, color } = nd;
      const c = nodeColors(color, isCollapsed);

      // Draw shape outline
      let outline;
      if (shape === 'leaf') {
        outline = document.createElementNS(NS, 'polygon');
        const hx = nh / 2;
        outline.setAttribute('points', `${hx},0 ${nw-hx},0 ${nw},${nh/2} ${nw-hx},${nh} ${hx},${nh} 0,${nh/2}`);
      } else if (shape === 'expr') {
        outline = document.createElementNS(NS, 'rect');
        outline.setAttribute('x', 0); outline.setAttribute('y', 0);
        outline.setAttribute('width', nw); outline.setAttribute('height', nh);
        outline.setAttribute('rx', nh / 2);
      } else {
        outline = document.createElementNS(NS, 'rect');
        outline.setAttribute('x', 0); outline.setAttribute('y', 0);
        outline.setAttribute('width', nw); outline.setAttribute('height', nh);
        outline.setAttribute('rx', 4);
      }
      outline.setAttribute('fill', c.fill); outline.setAttribute('stroke', c.stroke);
      outline.setAttribute('stroke-width', '1.5');
      g.appendChild(outline);

      const srcTextColor = '#000000';

      // Chevron arrow on the left for collapsible nodes
      if (hasChildren) {
        const ax = 9, ay = nh / 2;
        const arrow = document.createElementNS(NS, 'polygon');
        arrow.setAttribute('points', isCollapsed
          ? `${ax-5},${ay-5} ${ax-5},${ay+5} ${ax+5},${ay}`   // right-pointing
          : `${ax-5},${ay-3} ${ax+5},${ay-3} ${ax},${ay+5}`); // down-pointing
        arrow.setAttribute('fill', c.stroke);
        arrow.setAttribute('pointer-events', 'none');
        g.appendChild(arrow);
      }

      const textX = hasChildren ? ARROW_W : SRC_PAD_X;

      if (isCollapsed && src) {
        // Draw colored highlight rectangles behind text (from src_colors compact string)
        if (nd.src_colors) {
          // Parse compact run-length string like "_10 R5 B4 _4" and walk src in parallel
          // to track (line, col) position for each run.
          const COLOR_TAG = { R: 'red', B: 'blue' };
          let line = 0, col = 0, srcIdx = 0;
          nd.src_colors.split(' ').forEach(run => {
            const tag = run[0], count = parseInt(run.slice(1));
            if (tag !== '_') {
              // Colored run — never crosses a line boundary
              const pal = PALETTE[COLOR_TAG[tag]];
              if (pal) {
                const rect = document.createElementNS(NS, 'rect');
                rect.setAttribute('x', textX + col * CHAR_W);
                rect.setAttribute('y', SRC_PAD_Y + line * LINE_H);
                rect.setAttribute('width', count * CHAR_W);
                rect.setAttribute('height', LINE_H);
                rect.setAttribute('fill', pal.fill[1]);
                rect.setAttribute('rx', '2');
                rect.setAttribute('pointer-events', 'none');
                g.appendChild(rect);
              }
              col += count; srcIdx += count;
            } else {
              // Blank run — advance position, tracking newlines
              for (let k = 0; k < count; k++, srcIdx++) {
                if (src[srcIdx] === '\n') { line++; col = 0; } else { col++; }
              }
            }
          });
        }
        const text = document.createElementNS(NS, 'text');
        text.setAttribute('x', textX);
        text.setAttribute('y', SRC_PAD_Y + 13);
        text.setAttribute('font-family', 'monospace');
        text.setAttribute('font-size', '13');
        text.setAttribute('fill', srcTextColor);
        text.setAttribute('pointer-events', 'none');
        src.split('\n').forEach((line, i) => {
          const tspan = document.createElementNS(NS, 'tspan');
          tspan.setAttribute('x', textX);
          if (i > 0) tspan.setAttribute('dy', LINE_H);
          // SVG tspans need content to advance dy; blank lines must have \u00A0
          const m = line.match(/^( +)/);
          tspan.textContent = line === '' ? '\u00A0' : m ? '\u00A0'.repeat(m[1].length) + line.slice(m[1].length) : line;
          text.appendChild(tspan);
        });
        g.appendChild(text);
      } else {
        const text = document.createElementNS(NS, 'text');
        text.setAttribute('x', hasChildren ? textX : nw / 2);
        text.setAttribute('y', nh / 2 + 5);
        text.setAttribute('text-anchor', hasChildren ? 'start' : 'middle');
        text.setAttribute('font-family', 'monospace');
        text.setAttribute('font-size', '13');
        text.setAttribute('fill', '#1e3a5f');
        text.setAttribute('pointer-events', 'none');
        text.textContent = label;
        g.appendChild(text);
      }
    }

    function updateLines(svgLines) {
      const newLineMap = new Map(svgLines.map(l => [l.id, l]));

      for (const [id, els] of [...lineElements.entries()]) {
        if (!newLineMap.has(id)) {
          els.line.style.transition = `opacity ${ANIM_MS}ms ease`;
          els.line.style.opacity = '0';
          if (els.text) { els.text.style.transition = `opacity ${ANIM_MS}ms ease`; els.text.style.opacity = '0'; }
          setTimeout(() => { els.line.remove(); if (els.text) els.text.remove(); lineElements.delete(id); }, ANIM_MS);
        }
      }

      for (const { id, x1, y1, x2, y2, label, labelDx } of svgLines) {
        const lx = (x1 + x2) / 2 + (labelDx || 0);
        const ly = (y1 + y2) / 2 - 3;
        if (lineElements.has(id)) {
          const els = lineElements.get(id);
          const from = {
            x1: parseFloat(els.line.getAttribute('x1')), y1: parseFloat(els.line.getAttribute('y1')),
            x2: parseFloat(els.line.getAttribute('x2')), y2: parseFloat(els.line.getAttribute('y2')),
          };
          if (!firstRender && (from.x1 !== x1 || from.y1 !== y1 || from.x2 !== x2 || from.y2 !== y2))
            animateLinePos(els, from, { x1, y1, x2, y2 });
          else {
            els.line.setAttribute('x1', x1); els.line.setAttribute('y1', y1);
            els.line.setAttribute('x2', x2); els.line.setAttribute('y2', y2);
            if (els.text) { els.text.setAttribute('x', lx); els.text.setAttribute('y', ly); }
          }
        } else {
          const line = document.createElementNS(NS, 'line');
          line.setAttribute('x1', x1); line.setAttribute('y1', y1);
          line.setAttribute('x2', x2); line.setAttribute('y2', y2);
          line.setAttribute('stroke', '#94a3b8'); line.setAttribute('stroke-width', '1.5');
          linesGroup.appendChild(line);

          let text = null;
          if (label) {
            text = document.createElementNS(NS, 'text');
            text.setAttribute('x', lx); text.setAttribute('y', ly);
            text.setAttribute('text-anchor', 'middle');
            text.setAttribute('font-family', 'sans-serif'); text.setAttribute('font-size', '10');
            text.setAttribute('fill', '#64748b');
            text.textContent = label;
            linesGroup.appendChild(text);
          }

          lineElements.set(id, { line, text, labelDx: labelDx || 0 });
          if (!firstRender) {
            line.style.opacity = '0';
            line.style.transition = `opacity ${ANIM_MS}ms ease`;
            if (text) { text.style.opacity = '0'; text.style.transition = `opacity ${ANIM_MS}ms ease`; }
            requestAnimationFrame(() => requestAnimationFrame(() => {
              line.style.opacity = '1'; if (text) text.style.opacity = '1';
            }));
          }
        }
      }
    }

    // ---- main render loop ----
    function render() {
      const root = _currentRoot;
      const svgNodes = [], svgLines = [];
      if (isExpr(root)) {
        placeExpr(root, PAD, PAD, svgNodes, svgLines);
      } else {
        visit(root, PAD, PAD, svgNodes, svgLines);
      }

      const W = Math.max(...svgNodes.map(n => n.x + n.nw)) + PAD;
      const H = Math.max(...svgNodes.map(n => n.y + n.nh)) + PAD;
      svgEl.setAttribute('width', W); svgEl.setAttribute('height', H);

      if (!linesGroup) {
        linesGroup   = document.createElementNS(NS, 'g');
        nodesGroup   = document.createElementNS(NS, 'g');
        tooltipGroup = document.createElementNS(NS, 'g');
        svgEl.appendChild(linesGroup);
        svgEl.appendChild(nodesGroup);
        svgEl.appendChild(tooltipGroup);
      }

      updateLines(svgLines);

      const newIds = new Set(svgNodes.map(n => n.id));
      for (const [id, g] of [...nodeElements.entries()]) {
        if (!newIds.has(id)) {
          g.style.transition = `opacity ${ANIM_MS}ms ease`;
          g.style.opacity = '0';
          setTimeout(() => { g.remove(); nodeElements.delete(id); }, ANIM_MS);
        }
      }

      for (const nd of svgNodes) {
        const { id, x, y } = nd;
        if (nodeElements.has(id)) {
          const g = nodeElements.get(id);
          if (!firstRender) g.style.transition = `transform ${ANIM_MS}ms ease`;
          g.style.transform = `translate(${x}px, ${y}px)`;
          g._nd = nd;
          buildNodeContent(g, nd);
        } else {
          const g = document.createElementNS(NS, 'g');
          g.style.transform = `translate(${x}px, ${y}px)`;
          g._nd = nd;
          if (nd.hasChildren) {
            g.style.cursor = 'pointer';
            g.addEventListener('click', () => {
              hideTooltip();
              collapsed.has(id) ? collapsed.delete(id) : collapsed.add(id);
              _writePageHash();
              render();
            });
            g.addEventListener('mouseover', e => { e.stopPropagation(); scheduleTooltip(g._nd); });
            g.addEventListener('mouseout',  () => hideTooltip());
          }
          // Right-click context menu for all nodes with children
          g.addEventListener('contextmenu', e => {
            const curNd = g._nd;
            if (!curNd || !curNd.hasChildren) return;
            e.preventDefault();
            e.stopPropagation();
            hideTooltip();
            const items = [];
            if (_focusSection < 0 || _focusNodeId !== curNd.id) {
              items.push({ label: 'Focus on this subtree', action: () => _focusOnNode(sectionIdx, curNd.id) });
            }
            if (_focusSection >= 0) {
              items.push({ label: 'Show all', action: _showAll });
            }
            items.push({ label: _hideLeaves ? 'Show leaves' : 'Hide leaves', action: _toggleLeaves });
            items.push({ label: 'Copy SVG to clipboard', action: () => _copySVG(sectionIdx, curNd.id) });
            items.push({ label: 'Save SVG as file', action: () => _saveSVG(sectionIdx, curNd.id, curNd.label) });
            _buildContextMenu(e.clientX, e.clientY, items);
          });
          buildNodeContent(g, nd);
          nodesGroup.appendChild(g);
          nodeElements.set(id, g);
          if (!firstRender) {
            g.style.opacity = '0';
            g.style.transition = `opacity ${ANIM_MS}ms ease`;
            requestAnimationFrame(() => requestAnimationFrame(() => { g.style.opacity = '1'; }));
          }
        }
      }

      if (!firstRender) {
        _animating = true;
        clearTimeout(_animatingTimer);
        _animatingTimer = setTimeout(() => { _animating = false; }, ANIM_MS);
      }
      firstRender = false;
    }

    function renderWith(root) {
      _currentRoot = root;
      // Clear existing DOM elements to force full re-render
      for (const [, g] of nodeElements) g.remove();
      nodeElements.clear();
      for (const [, els] of lineElements) { els.line.remove(); if (els.text) els.text.remove(); }
      lineElements.clear();
      firstRender = true;
      render();
    }

    function exportSubtreeSVG(nodeId) {
      const subtree = _findNode(astData, nodeId);
      if (!subtree) return null;
      // Create a hidden SVG, render the subtree into it with the same
      // collapsed/expanded state as the current view
      const tmpSvg = document.createElementNS(NS, 'svg');
      tmpSvg.style.cssText = 'position:absolute;left:-9999px;top:-9999px;';
      document.body.appendChild(tmpSvg);
      init(tmpSvg, subtree, collapsed);
      _instances.pop();
      tmpSvg.removeAttribute('style');
      // Also strip inline styles from inner <g> elements (transition/transform)
      // and convert transforms to static positions for a clean static SVG
      tmpSvg.querySelectorAll('g[style]').forEach(g => {
        const m = g.style.transform.match(/translate\((.+?)px,\s*(.+?)px\)/);
        if (m) {
          g.removeAttribute('style');
          g.setAttribute('transform', 'translate(' + m[1] + ',' + m[2] + ')');
        }
      });
      const serializer = new XMLSerializer();
      const raw = serializer.serializeToString(tmpSvg);
      tmpSvg.remove();
      return '<?xml version="1.0" encoding="UTF-8"?>\n' + raw;
    }

    // ---- bootstrap ----
    if (initialCollapsed) {
      // Reuse existing _id values and collapsed state (e.g. for SVG export)
      initialCollapsed.forEach(id => collapsed.add(id));
    } else {
      assignIds(astData);
      initCollapsed(astData);
    }

    const inst = {
      svgEl, astData, sectionIdx, headerEl, collapsed, render, renderWith,
      exportSubtreeSVG,
    };
    _instances.push(inst);

    render();
  }

  // Called after all sections have been rendered to restore hash state
  function restoreFromHash() {
    if (_readPageHash()) {
      // Re-render all instances with restored collapsed state
      for (const inst of _instances) {
        inst.renderWith(inst.astData);
      }
      if (_focusSection >= 0) {
        _applyFocus();
      }
    }
  }

  // Dismiss context menu on click anywhere
  if (typeof document !== 'undefined') {
    document.addEventListener('click', _removeContextMenu);
  }

  global.SPyAstViz = { render: init, restoreFromHash: restoreFromHash, _instances: _instances };

})(typeof window !== 'undefined' ? window : this);
