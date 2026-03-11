import textwrap
from typing import Any

import pytest

from spy.backend.html import HTMLBackend
from spy.parser import Parser
from spy.util import print_diff


def dump_node(d: dict[str, Any], indent: int = 0) -> str:
    """
    Pretty-print a node_to_dict result into a compact text format:
        label [shape/color] *expanded
          attr: child_label [shape/color]
          attr: ...
    """
    parts = []
    prefix = "    " * indent
    flags = f"{d['shape']}, {d['color']}"
    if d.get("src_colors"):
        flags += f", src_colors={d['src_colors']}"
    header = f"{prefix}<{d['label']}> ({flags})"
    parts.append(header)
    for child in d["children"]:
        attr = child["attr"]
        node = child["node"]
        child_str = dump_node(node, indent + 1)
        # Replace the leading indentation of the first line with "attr: "
        child_prefix = "    " * (indent + 1)
        child_str = f"{child_prefix}{attr}: {child_str.lstrip()}"
        parts.append(child_str)
    return "\n".join(parts)


@pytest.mark.usefixtures("init")
class TestHTMLBackend:
    @pytest.fixture
    def init(self, tmpdir):
        self.tmpdir = tmpdir

    def parse(self, src: str):
        f = self.tmpdir.join("test.spy")
        src = textwrap.dedent(src)
        f.write(src)
        parser = Parser(src, str(f))
        return parser.parse()

    def to_dict(self, src: str) -> dict[str, Any]:
        mod = self.parse(src)
        b = HTMLBackend()
        return b.node_to_dict(mod)

    def get_node(self, d: dict[str, Any], label: str) -> dict[str, Any]:
        if d["label"] == label:
            return d
        for child in d["children"]:
            result = self.get_node(child["node"], label)
            if result is not None:
                return result
        return None

    def assert_dump(self, d: dict[str, Any], expected: str) -> None:
        dumped = dump_node(d)
        expected = textwrap.dedent(expected).strip()
        if "{tmpdir}" in expected:
            expected = expected.format(tmpdir=self.tmpdir)
        if dumped != expected:
            print_diff(expected, dumped, "expected", "got")
            pytest.fail("assert_dump failed")

    def test_simple_funcdef(self):
        d = self.to_dict("""
        def foo() -> void:
            pass
        """)
        expected = """
        <Module> (stmt, default)
            filename: <'{tmpdir}/test.spy'> (leaf, emerald)
            decls[0]: <GlobalFuncDef> (stmt, default)
                funcdef: <FuncDef: red foo> (stmt, default)
                    color: <'red'> (leaf, emerald)
                    kind: <'plain'> (leaf, emerald)
                    name: <'foo'> (leaf, emerald)
                    return_type: <Name: void> (expr, amber)
                        id: <'void'> (leaf, emerald)
                    body[0]: <Pass> (stmt, default)
        """
        self.assert_dump(d, expected)

    def test_funcdef_with_exprs(self):
        d = self.to_dict("""
        def foo(x: i32) -> i32:
            return x + 1
        """)
        funcdef = self.get_node(d, "FuncDef: red foo")
        expected = """
        <FuncDef: red foo> (stmt, default)
            color: <'red'> (leaf, emerald)
            kind: <'plain'> (leaf, emerald)
            name: <'foo'> (leaf, emerald)
            args[0]: <FuncArg: x simple> (stmt, default)
                name: <'x'> (leaf, emerald)
                type: <Name: i32> (expr, amber)
                    id: <'i32'> (leaf, emerald)
                kind: <'simple'> (leaf, emerald)
            return_type: <Name: i32> (expr, amber)
                id: <'i32'> (leaf, emerald)
            body[0]: <Return> (stmt, default)
                value: <BinOp: +> (expr, amber)
                    op: <'+'> (leaf, emerald)
                    left: <Name: x> (expr, amber)
                        id: <'x'> (leaf, emerald)
                    right: <Constant: 1> (expr, amber)
                        value: <1> (leaf, emerald)
        """
        self.assert_dump(funcdef, expected)
