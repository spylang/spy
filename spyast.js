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

  function init(svgEl, astData) {
    // ---- per-instance state ----
    let _idCounter = 0;
    const collapsed = new Set();
    const nodeElements = new Map();
    const lineElements = new Map();
    let linesGroup = null, nodesGroup = null, tooltipGroup = null;
    let firstRender = true;
    let _tooltipTimer = null;
    let _animating = false, _animatingTimer = null;

    // ---- generic node accessors ----
    function isExpr(node)      { return !!node.expr; }
    function labelOf(node)     { return node.label || node.type; }
    function childrenOf(node)  { return node.children || []; }
    function canCollapse(node) { return childrenOf(node).length > 0; }

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
      const ch = childrenOf(node);
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
      const ch = childrenOf(node);
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
      const children = childrenOf(node);
      const hasChildren = children.length > 0;
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
        tspan.textContent = line;
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
        // Draw colored highlight rectangles behind text (from src_colors)
        if (nd.src_colors) {
          nd.src_colors.forEach(sc => {
            const pal = PALETTE[sc.color];
            if (!pal) return;
            const rx = textX + sc.start * CHAR_W;
            const ry = SRC_PAD_Y + sc.line * LINE_H;
            const rw = (sc.end - sc.start) * CHAR_W;
            const rect = document.createElementNS(NS, 'rect');
            rect.setAttribute('x', rx);
            rect.setAttribute('y', ry);
            rect.setAttribute('width', rw);
            rect.setAttribute('height', LINE_H);
            rect.setAttribute('fill', pal.fill[1]);
            rect.setAttribute('rx', '2');
            rect.setAttribute('pointer-events', 'none');
            g.appendChild(rect);
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
          // Replace leading spaces with non-breaking spaces to preserve indentation
          const m = line.match(/^( +)/);
          tspan.textContent = m ? '\u00A0'.repeat(m[1].length) + line.slice(m[1].length) : line;
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
      const svgNodes = [], svgLines = [];
      visit(astData, PAD, PAD, svgNodes, svgLines);

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
              writeHash();
              render();
            });
            g.addEventListener('mouseover', e => { e.stopPropagation(); scheduleTooltip(g._nd); });
            g.addEventListener('mouseout',  () => hideTooltip());
          }
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

    // ---- hash state ----
    function writeHash() {
      const ids = [...collapsed].sort((a, b) => a - b).join(',');
      history.replaceState(null, '', '#' + ids);
    }

    function readHash() {
      const hash = location.hash.slice(1);
      if (!hash) return false;
      collapsed.clear();
      hash.split(',').filter(Boolean).forEach(s => collapsed.add(Number(s)));
      return true;
    }

    // ---- bootstrap ----
    assignIds(astData);
    if (!readHash()) initCollapsed(astData);
    render();
  }

  global.SPyAstViz = { render: init };

})(typeof window !== 'undefined' ? window : this);
