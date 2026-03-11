import textwrap
from typing import Any

import pytest

from spy.backend.html import HTMLBackend
from spy.cli.commands.colorize import colorize_mod
from spy.parser import Parser
from spy.util import print_diff
from spy.vm.function import W_ASTFunc
from spy.vm.vm import SPyVM


def dump_node(d: dict[str, Any], indent: int = 0) -> str:
    """
    Pretty-print a node_to_dict result into a compact text format:
        <label> (shape, color)
            attr: <child_label> (shape, color)
    """
    parts = []
    prefix = "    " * indent
    flags = f"{d['shape']}, {d['color']}"
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
        self.vm = SPyVM()
        self.vm.path.append(str(self.tmpdir))

    def write_src(self, src: str) -> None:
        f = self.tmpdir.join("test.spy")
        src = textwrap.dedent(src)
        f.write(src)

    def parse(self, src: str) -> dict[str, Any]:
        self.write_src(src)
        parser = Parser(textwrap.dedent(src), str(self.tmpdir.join("test.spy")))
        mod = parser.parse()
        b = HTMLBackend()
        return b.node_to_dict(mod)

    def redshift(self, src: str) -> dict[str, Any]:
        self.write_src(src)
        self.vm.import_("test")
        self.vm.redshift(error_mode="eager")
        b = HTMLBackend(vm=self.vm, is_redshifted=True)
        for fqn, w_obj in self.vm.fqns_by_modname("test"):
            if isinstance(w_obj, W_ASTFunc) and w_obj.color == "red":
                return b.node_to_dict(w_obj.funcdef)
        raise ValueError("no red function found")

    def colorize(self, src: str) -> dict[str, Any]:
        self.write_src(src)
        orig_mod = colorize_mod(self.vm, "test", use_spyc=False, error_mode="eager")
        b = HTMLBackend(ast_color_map=self.vm.ast_color_map)
        return b.node_to_dict(orig_mod)

    def get_node(self, d: dict[str, Any], label: str) -> dict[str, Any]:
        def find(d: dict[str, Any]) -> Any:
            if d["label"] == label:
                return d
            for child in d["children"]:
                result = find(child["node"])
                if result is not None:
                    return result
            return None

        result = find(d)
        if result is None:
            raise KeyError(label)
        return result

    def format_src(self, src: str, src_colors: list[dict[str, Any]]) -> str:
        """
        Apply src_colors to the given src. Return a string like:
            [R]x[R] + [B]1[/B]
        """
        COLOR_TAG = {"red": "R", "blue": "B"}
        lines = src.split("\n")
        for sc in sorted(src_colors, key=lambda c: (c["line"], -c["start"])):
            line = lines[sc["line"]]
            tag = COLOR_TAG[sc["color"]]
            start, end = sc["start"], sc["end"]
            line = f"{line[:start]}[{tag}]{line[start:end]}[/{tag}]{line[end:]}"
            lines[sc["line"]] = line
        return "\n".join(lines)

    def assert_dump(self, d: dict[str, Any], expected: str) -> None:
        dumped = dump_node(d)
        expected = textwrap.dedent(expected).strip()
        if "{tmpdir}" in expected:
            expected = expected.format(tmpdir=self.tmpdir)
        if dumped != expected:
            print_diff(expected, dumped, "expected", "got")
            pytest.fail("assert_dump failed")

    def test_simple_funcdef(self):
        d = self.parse("""
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
        d = self.parse("""
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

    def test_redshift(self):
        d = self.redshift("""
        def foo(x: i32) -> i32:
            return x + 1
        """)
        ret = self.get_node(d, "Return")
        expected = """
        <Return> (stmt, default)
            value: <Call> (expr, amber)
                func: <FQNConst> (expr, amber)
                    fqn: <operator::i32_add> (leaf, emerald)
                args[0]: <NameLocalDirect> (expr, amber)
                    sym: <x> (leaf, emerald)
                args[1]: <Constant: 1> (expr, amber)
                    value: <1> (leaf, emerald)
        """
        self.assert_dump(ret, expected)

    def test_colorize(self):
        d = self.colorize("""
        def foo(x: i32) -> i32:
            return x + 1
        """)
        ret = self.get_node(d, "Return")
        # "x + 1" --> red
        # "x"     --> red
        # "1"     --> blue
        expected = """
        <Return> (stmt, default)
            value: <BinOp: +> (expr, red)
                op: <'+'> (leaf, emerald)
                left: <Name: x> (expr, red)
                    id: <'x'> (leaf, emerald)
                right: <Constant: 1> (expr, blue)
                    value: <1> (leaf, emerald)
        """
        self.assert_dump(ret, expected)

    def test_src_color(self):
        d = self.colorize("""
        def foo(x: i32) -> i32:
            return x + 1
        """)
        binop = self.get_node(d, "BinOp: +")
        src = binop["src"]
        src_colors = binop["src_colors"]
        fmt = self.format_src(src, src_colors)
        assert src == "x + 1"
        assert fmt == "[R]x[/R] + [B]1[/B]"
