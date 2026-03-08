import json
from toyast import EXAMPLE, Module, Assign, If, Const, BinOp, Name, FuncDef, FuncArg, Return


def ch(attr, node):
    return {'attr': attr, 'node': to_dict(node)}

def name_leaf(name):
    return {'type': 'Name', 'src': name, 'label': name, 'expr': True, 'children': []}

def to_dict(node):
    if isinstance(node, Module):
        return {'type': 'Module', 'src': node.src, 'label': 'Module',
                'expr': False, 'startExpanded': True,
                'children': [{'attr': f'body[{i}]' if len(node.body) > 1 else 'body', 'node': to_dict(s)}
                             for i, s in enumerate(node.body)]}
    if isinstance(node, Assign):
        return {'type': 'Assign', 'src': node.src, 'label': 'Assign',
                'expr': False,
                'children': [{'attr': 'target', 'node': name_leaf(node.target)},
                             ch('value', node.value)]}
    if isinstance(node, If):
        then_ch = [{'attr': f'then[{i}]' if len(node.then_body) > 1 else 'then', 'node': to_dict(s)}
                   for i, s in enumerate(node.then_body)]
        else_ch = [{'attr': f'else[{i}]' if len(node.else_body) > 1 else 'else', 'node': to_dict(s)}
                   for i, s in enumerate(node.else_body)]
        return {'type': 'If', 'src': node.src, 'label': 'If',
                'expr': False,
                'children': [ch('test', node.test), *then_ch, *else_ch]}
    if isinstance(node, BinOp):
        return {'type': 'BinOp', 'src': node.src, 'label': f'BinOp {node.op}',
                'expr': True,
                'children': [ch('left', node.left), ch('right', node.right)]}
    if isinstance(node, Const):
        return {'type': 'Const', 'src': node.src, 'label': f'Const {node.value}',
                'expr': True, 'children': []}
    if isinstance(node, Name):
        return {'type': 'Name', 'src': node.name, 'label': node.name,
                'expr': True, 'children': []}
    if isinstance(node, Return):
        return {'type': 'Return', 'src': node.src, 'label': 'Return',
                'expr': False,
                'children': [ch('value', node.value)]}
    if isinstance(node, FuncArg):
        return {'type': 'FuncArg', 'src': node.src, 'label': f'FuncArg {node.name}',
                'expr': False,
                'children': [{'attr': 'name', 'node': name_leaf(node.name)},
                             ch('type', node.type)]}
    if isinstance(node, FuncDef):
        args_ch = [{'attr': f'args[{i}]' if len(node.args) > 1 else 'args', 'node': to_dict(a)}
                   for i, a in enumerate(node.args)]
        body_ch = [{'attr': f'body[{i}]' if len(node.body) > 1 else 'body', 'node': to_dict(s)}
                   for i, s in enumerate(node.body)]
        return {'type': 'FuncDef', 'src': node.src, 'label': f'FuncDef {node.name}',
                'expr': False,
                'children': [{'attr': 'name', 'node': name_leaf(node.name)},
                             *args_ch,
                             ch('return_type', node.return_type),
                             *body_ch]}
    raise ValueError(f'Unknown node: {node}')


ast_json = json.dumps(to_dict(EXAMPLE))

with open('/tmp/mermaid/spyast.js') as f:
    viz_js = f.read()

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
{viz_js}
    ToyAstViz.render(document.getElementById('diagram'), {ast_json});
  </script>
</body>
</html>
"""

with open('/tmp/mermaid/output.html', 'w') as f:
    f.write(html)

print("Written output.html")
