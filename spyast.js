// spyast.js — standalone AST visualizer
// Usage: ToyAstViz.render(svgElement, astData)
(function (global) {
  'use strict';

  const NODE_W = 110, NODE_H = 28;
  const X_INDENT = 120, ROW_GAP = 16;
  const EXPR_H_GAP = 16, EXPR_V_GAP = 30, PAD = 20;
  const CHAR_W = 7.8, LINE_H = 18, SRC_PAD_X = 10, SRC_PAD_Y = 8;
  const NS = 'http://www.w3.org/2000/svg';
  const ANIM_MS = 300;

  function init(svgEl, astData) {
    // ---- per-instance state ----
    let _idCounter = 0;
    const collapsed = new Set();
    const nodeElements = new Map();
    const lineElements = new Map();
    let linesGroup = null, nodesGroup = null, tooltipGroup = null;
    let firstRender = true;
    let _tooltipTimer = null;

    // ---- id assignment ----
    function assignIds(node) {
    node._id = _idCounter++;
    if (node.type === 'Module')  node.body.forEach(assignIds);
    if (node.type === 'Assign')  { assignIds(node.target); assignIds(node.value); }
    if (node.type === 'If')      { assignIds(node.test); node.then_body.forEach(assignIds); node.else_body.forEach(assignIds); }
    if (node.type === 'BinOp')   { assignIds(node.left); assignIds(node.right); }
    if (node.type === 'FuncDef') { assignIds(node.name_node); node.args.forEach(assignIds); assignIds(node.return_type); node.body.forEach(assignIds); }
    if (node.type === 'FuncArg') { assignIds(node.argname_node); assignIds(node.argtype); }
    if (node.type === 'Return')  { assignIds(node.value); }
    }

    // ---- helpers ----
    function isExpr(node)     { return node.type === 'BinOp' || node.type === 'Const' || node.type === 'Name'; }
    function canCollapse(node){ return node.type === 'BinOp' || childrenOf(node).length > 0; }

    function labelOf(node) {
    if (node.type === 'BinOp')   return `BinOp: ${node.op}`;
    if (node.type === 'Const')   return `Const: ${node.value}`;
    if (node.type === 'Name')    return node.name;
    if (node.type === 'FuncDef') return `FuncDef ${node.name}`;
    if (node.type === 'Return')  return 'Return';
    if (node.type === 'FuncArg') return `FuncArg ${node.argname}`;
    return node.type;
    }

    function childrenOf(node) {
    if (node.type === 'Module')
      return node.body.map((n, i) => ({ attr: node.body.length > 1 ? `body[${i}]` : 'body', node: n }));
    if (node.type === 'Assign')
      return [{ attr: 'target', node: node.target }, { attr: 'value', node: node.value }];
    if (node.type === 'If')
      return [
        { attr: 'test', node: node.test },
        ...node.then_body.map((n, i) => ({ attr: node.then_body.length > 1 ? `then[${i}]` : 'then', node: n })),
        ...node.else_body.map((n, i) => ({ attr: node.else_body.length > 1 ? `else[${i}]` : 'else', node: n })),
      ];
    if (node.type === 'FuncDef')
      return [
        { attr: 'name', node: node.name_node },
        ...node.args.map((n, i) => ({ attr: node.args.length > 1 ? `args[${i}]` : 'args', node: n })),
        { attr: 'return_type', node: node.return_type },
        ...node.body.map((n, i) => ({ attr: node.body.length > 1 ? `body[${i}]` : 'body', node: n })),
      ];
    if (node.type === 'FuncArg')
      return [{ attr: 'name', node: node.argname_node }, { attr: 'type', node: node.argtype }];
    if (node.type === 'Return')
      return [{ attr: 'value', node: node.value }];
    return [];
    }

    // ---- collapsed init ----
    function initCollapsed(node) {
    if (canCollapse(node) && node.type !== 'Module') collapsed.add(node._id);
    if (node.type === 'Module')  node.body.forEach(initCollapsed);
    if (node.type === 'Assign')  { initCollapsed(node.target); initCollapsed(node.value); }
    if (node.type === 'If')      { initCollapsed(node.test); node.then_body.forEach(initCollapsed); node.else_body.forEach(initCollapsed); }
    if (node.type === 'BinOp')   { initCollapsed(node.left); initCollapsed(node.right); }
    if (node.type === 'FuncDef') { initCollapsed(node.name_node); node.args.forEach(initCollapsed); initCollapsed(node.return_type); node.body.forEach(initCollapsed); }
    if (node.type === 'FuncArg') { initCollapsed(node.argname_node); initCollapsed(node.argtype); }
    if (node.type === 'Return')  { initCollapsed(node.value); }
    }

    // ---- layout ----
    function nodeSize(node) {
    if (!collapsed.has(node._id) || !canCollapse(node))
      return { w: NODE_W, h: NODE_H };
    const lines = (node.src || '').split('\n');
    const maxLen = Math.max(...lines.map(l => l.length));
    return {
      w: Math.max(NODE_W, Math.ceil(maxLen * CHAR_W) + 2 * SRC_PAD_X),
      h: lines.length * LINE_H + 2 * SRC_PAD_Y,
    };
    }

    function measureExpr(node) {
    if (collapsed.has(node._id) || node.type !== 'BinOp') return nodeSize(node).w;
    return measureExpr(node.left) + EXPR_H_GAP + measureExpr(node.right);
    }

    function placeExpr(node, leftX, y, svgNodes, svgLines) {
    const totalW = measureExpr(node);
    const { w: nw, h: nh } = nodeSize(node);
    const nodeX = leftX + (totalW - nw) / 2;
    const isCollapsed = collapsed.has(node._id);
    svgNodes.push({ x: nodeX, y, nw, nh, label: labelOf(node), src: node.src,
                    id: node._id, hasChildren: node.type === 'BinOp', isCollapsed, expr: true });

    if (node.type === 'BinOp' && !isCollapsed) {
      const childY = y + nh + EXPR_V_GAP;
      const leftW  = measureExpr(node.left);
      const rightW = measureExpr(node.right);
      const { w: lnw } = nodeSize(node.left);
      const { w: rnw } = nodeSize(node.right);
      const leftChildX  = leftX + (leftW - lnw) / 2;
      const rightChildX = leftX + leftW + EXPR_H_GAP + (rightW - rnw) / 2;
      const parentCx = nodeX + nw / 2;
      const midY     = y + nh + EXPR_V_GAP / 2;
      const lChildCx = leftChildX  + lnw / 2;
      const rChildCx = rightChildX + rnw / 2;
      svgLines.push({ x1: parentCx, y1: y + nh, x2: parentCx, y2: midY,   id: `evs-${node._id}` });
      svgLines.push({ x1: lChildCx, y1: midY,   x2: parentCx, y2: midY,   label: 'left',  id: `ehl-${node._id}` });
      svgLines.push({ x1: parentCx, y1: midY,   x2: rChildCx, y2: midY,   label: 'right', id: `ehr-${node._id}` });
      svgLines.push({ x1: lChildCx, y1: midY,   x2: lChildCx, y2: childY, id: `el-${node._id}-${node.left._id}` });
      svgLines.push({ x1: rChildCx, y1: midY,   x2: rChildCx, y2: childY, id: `er-${node._id}-${node.right._id}` });
      const lb = placeExpr(node.left,  leftX,                      childY, svgNodes, svgLines);
      const rb = placeExpr(node.right, leftX + leftW + EXPR_H_GAP, childY, svgNodes, svgLines);
      return Math.max(lb, rb);
    }
    return y + nh;
    }

    function visit(node, x, y, svgNodes, svgLines) {
    const { w: nw, h: nh } = nodeSize(node);
    const children = childrenOf(node);
    const hasChildren = children.length > 0;
    const isCollapsed = collapsed.has(node._id);
    svgNodes.push({ x, y, nw, nh, label: labelOf(node), src: node.src,
                    id: node._id, hasChildren, isCollapsed, expr: false });
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
    rect.setAttribute('fill',   nd.expr ? '#fef3c7' : '#e0e7ff');
    rect.setAttribute('stroke', nd.expr ? '#d97706' : '#6366f1');
    rect.setAttribute('stroke-width', '1');
    rect.setAttribute('filter', 'drop-shadow(0 2px 4px rgba(0,0,0,.15))');
    tooltipGroup.appendChild(rect);

    const text = document.createElementNS(NS, 'text');
    text.setAttribute('x', tx + SRC_PAD_X);
    text.setAttribute('y', ty + SRC_PAD_Y + 13);
    text.setAttribute('font-family', 'monospace');
    text.setAttribute('font-size', '13');
    text.setAttribute('fill', nd.expr ? '#78350f' : '#312e81');
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

    function scheduleTooltip(nd) { _tooltipTimer = setTimeout(() => showTooltip(nd), 600); }
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
    function nodeColors(expr, isCollapsed) {
    return {
      fill:   expr ? (isCollapsed ? '#fef3c7' : '#fef9c3') : (isCollapsed ? '#e0e7ff' : '#dbeafe'),
      stroke: expr ? (isCollapsed ? '#d97706' : '#ca8a04') : (isCollapsed ? '#6366f1' : '#3b82f6'),
    };
    }

    function buildNodeContent(g, nd) {
    while (g.firstChild) g.removeChild(g.firstChild);
    const { nw, nh, label, src, hasChildren, isCollapsed, expr } = nd;
    const c = nodeColors(expr, isCollapsed);

    const rect = document.createElementNS(NS, 'rect');
    rect.setAttribute('x', 0); rect.setAttribute('y', 0);
    rect.setAttribute('width', nw); rect.setAttribute('height', nh);
    rect.setAttribute('rx', 4);
    rect.setAttribute('fill', c.fill); rect.setAttribute('stroke', c.stroke);
    rect.setAttribute('stroke-width', '1.5');
    g.appendChild(rect);

    if (isCollapsed && src) {
      const text = document.createElementNS(NS, 'text');
      text.setAttribute('x', SRC_PAD_X);
      text.setAttribute('y', SRC_PAD_Y + 13);
      text.setAttribute('font-family', 'monospace');
      text.setAttribute('font-size', '13');
      text.setAttribute('fill', expr ? '#78350f' : '#312e81');
      text.setAttribute('pointer-events', 'none');
      src.split('\n').forEach((line, i) => {
        const tspan = document.createElementNS(NS, 'tspan');
        tspan.setAttribute('x', SRC_PAD_X);
        if (i > 0) tspan.setAttribute('dy', LINE_H);
        tspan.textContent = line;
        text.appendChild(tspan);
      });
      g.appendChild(text);
    } else {
      const text = document.createElementNS(NS, 'text');
      text.setAttribute('x', nw / 2);
      text.setAttribute('y', nh / 2 + 5);
      text.setAttribute('text-anchor', 'middle');
      text.setAttribute('font-family', 'monospace');
      text.setAttribute('font-size', '13');
      text.setAttribute('fill', '#1e3a5f');
      text.setAttribute('pointer-events', 'none');
      text.textContent = (hasChildren ? (isCollapsed ? '▶ ' : '▼ ') : '') + label;
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
      linesGroup    = document.createElementNS(NS, 'g');
      nodesGroup    = document.createElementNS(NS, 'g');
      tooltipGroup  = document.createElementNS(NS, 'g');
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
            collapsed.has(id) ? collapsed.delete(id) : collapsed.add(id);
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

    firstRender = false;
  }

  // ---- bootstrap ----
  assignIds(astData);
  initCollapsed(astData);
  render();
  }

  global.ToyAstViz = { render: init };

})(typeof window !== 'undefined' ? window : this);
