import json
from toyast import EXAMPLE, Module, Assign, If, Const, BinOp, Name, FuncDef, FuncArg, Return


def to_dict(node):
    if isinstance(node, Module):
        return {'type': 'Module', 'src': node.src, 'body': [to_dict(s) for s in node.body]}
    if isinstance(node, Assign):
        return {'type': 'Assign', 'src': node.src,
                'target': {'type': 'Name', 'src': node.target, 'name': node.target},
                'value': to_dict(node.value)}
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
    if isinstance(node, Return):
        return {'type': 'Return', 'src': node.src, 'value': to_dict(node.value)}
    if isinstance(node, Name):
        return {'type': 'Name', 'src': node.name, 'name': node.name}
    if isinstance(node, FuncArg):
        return {'type': 'FuncArg', 'src': node.src, 'argname': node.name,
                'argname_node': {'type': 'Name', 'src': node.name, 'name': node.name},
                'argtype': to_dict(node.type)}
    if isinstance(node, FuncDef):
        return {'type': 'FuncDef', 'src': node.src, 'name': node.name,
                'name_node': {'type': 'Name', 'src': node.name, 'name': node.name},
                'args': [to_dict(a) for a in node.args],
                'return_type': to_dict(node.return_type),
                'body': [to_dict(s) for s in node.body]}
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
