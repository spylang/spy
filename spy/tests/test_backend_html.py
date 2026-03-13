import textwrap
from typing import Any

import pytest

from spy.backend.html import HTMLBackend
from spy.cli.commands.colorize import colorize_mod
from spy.parser import Parser
from spy.util import print_diff
from spy.vm.function import W_ASTFunc
from spy.vm.vm import SPyVM


def dump_node(d: dict[str, Any], indent: int = 0, show_src: bool = False) -> str:
    """
    Pretty-print a node_to_dict result into a compact text format:
        <label> (shape, color)
            attr: <child_label> (shape, color)

    If show_src=True, source lines are shown after the header:
        <label> (shape, color)
            | line 1 of source
            | line 2 of source
            attr: <child_label> (shape, color)
    """
    parts = []
    prefix = "    " * indent
    flags = f"{d['shape']}, {d['color']}"
    header = f"{prefix}<{d['label']}> ({flags})"
    parts.append(header)
    if show_src:
        src = d.get("src", "")
        if src:
            for line in src.split("\n"):
                parts.append(f"{prefix}    | {line}")
    for child in d["children"]:
        attr = child["attr"]
        node = child["node"]
        child_str = dump_node(node, indent + 1, show_src=show_src)
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

    def format_src(self, src: str, src_colors: str) -> str:
        """
        Apply src_colors compact string to src. Return a string like:
            [R]x[/R] + [B]1[/B]
        """
        TAG_OPEN = {"R": "[R]", "B": "[B]"}
        TAG_CLOSE = {"R": "[/R]", "B": "[/B]"}
        result = []
        src_idx = 0
        for run in src_colors.split(" "):
            tag, count = run[0], int(run[1:])
            chunk = src[src_idx : src_idx + count]
            if tag == "_":
                result.append(chunk)
            else:
                result.append(f"{TAG_OPEN[tag]}{chunk}{TAG_CLOSE[tag]}")
            src_idx += count
        result.append(src[src_idx:])
        return "".join(result)

    def assert_dump(
        self, d: dict[str, Any], expected: str, show_src: bool = False
    ) -> None:
        dumped = dump_node(d, show_src=show_src)
        expected = textwrap.dedent(expected).strip()
        if "{tmpdir}" in expected:
            expected = expected.format(tmpdir=self.tmpdir)
        if dumped != expected:
            print_diff(expected, dumped, "expected", "got")
            pytest.fail("assert_dump failed")

    def test_parse_simple(self):
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

    def test_parse_exprs(self):
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

    def test_parse_show_src(self):
        d = self.parse("""
        def foo(x: i32) -> i32:
            return x + 1
        """)
        funcdef = self.get_node(d, "FuncDef: red foo")
        expected = """
        <FuncDef: red foo> (stmt, default)
            | def foo(x: i32) -> i32:
            |     return x + 1
            color: <'red'> (leaf, emerald)
            kind: <'plain'> (leaf, emerald)
            name: <'foo'> (leaf, emerald)
            args[0]: <FuncArg: x simple> (stmt, default)
                | x: i32
                name: <'x'> (leaf, emerald)
                type: <Name: i32> (expr, amber)
                    | i32
                    id: <'i32'> (leaf, emerald)
                kind: <'simple'> (leaf, emerald)
            return_type: <Name: i32> (expr, amber)
                | i32
                id: <'i32'> (leaf, emerald)
            body[0]: <Return> (stmt, default)
                | return x + 1
                value: <BinOp: +> (expr, amber)
                    | x + 1
                    op: <'+'> (leaf, emerald)
                    left: <Name: x> (expr, amber)
                        | x
                        id: <'x'> (leaf, emerald)
                    right: <Constant: 1> (expr, amber)
                        | 1
                        value: <1> (leaf, emerald)
        """
        self.assert_dump(funcdef, expected, show_src=True)

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

    def test_redshift_show_src(self):
        d = self.redshift("""
        def foo(x: i32) -> i32:
            return x + 1
        """)
        ret = self.get_node(d, "Return")
        expected = """
        <Return> (stmt, default)
            | return x + 1
            value: <Call> (expr, amber)
                | x + 1
                func: <FQNConst> (expr, amber)
                    | `operator::i32_add`
                    fqn: <operator::i32_add> (leaf, emerald)
                args[0]: <NameLocalDirect> (expr, amber)
                    | x
                    sym: <x> (leaf, emerald)
                args[1]: <Constant: 1> (expr, amber)
                    | 1
                    value: <1> (leaf, emerald)
        """
        self.assert_dump(ret, expected, show_src=True)

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

    def test_colorize_src_colors(self):
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

    def test_nested_multiline_src_is_dedented(self):
        d = self.colorize("""
        def foo(x: i32) -> i32:
            for i in range(x):
                pass
            return x + 1
        """)
        # For is nested at col_start > 0 and is multi-line:
        # its src must be dedented and src_colors must align with it
        for_node = self.get_node(d, "For")
        src = for_node["src"]
        src_colors = for_node.get("src_colors", "")
        assert src == "for i in range(x):\n    pass"
        assert src_colors == "_9 B5 R3 _10"
        fmt = self.format_src(src, src_colors)
        assert fmt == "for i in [B]range[/B][R](x)[/R]:\n    pass"

    def test_colorize_src_colors_no_overflow(self):
        d = self.colorize("""
        from operator import OpSpec

        @struct
        class Point:
            x: i32
            y: i32
            def sum(self) -> i32:
                return self.x + self.y
        """)
        classdef = self.get_node(d, "ClassDef: struct Point")
        # ClassDef src comes from body_loc, which includes the full class body
        assert classdef["src"] == (
            "class Point:\n"
            "    x: i32\n"
            "    y: i32\n"
            "    def sum(self) -> i32:\n"
            "        return self.x + self.y"
        )
        # The method inside should still have its own src_colors
        funcdef = self.get_node(d, "FuncDef: red sum")
        assert funcdef.get("src_colors", "") != ""

    def test_classdef_src_uses_body_loc(self):
        d = self.parse("""
        @struct
        class Point:
            x: i32
            y: i32
        """)
        expected_src = "class Point:\n    x: i32\n    y: i32"
        classdef = self.get_node(d, "ClassDef: struct Point")
        assert classdef["src"] == expected_src
        globalclassdef = self.get_node(d, "GlobalClassDef")
        assert globalclassdef["src"] == expected_src

    def test_str_const_shortrepr(self):
        d = self.parse("""
        def foo() -> void:
            x: str = 'hello'
        """)
        vardef = self.get_node(d, "VarDef")
        expected = """
        <VarDef> (stmt, default)
            kind: <None> (leaf, emerald)
            name: <StrConst: 'x'> (expr, amber)
                value: <'x'> (leaf, emerald)
            type: <Name: str> (expr, amber)
                id: <'str'> (leaf, emerald)
            value: <StrConst: 'hello'> (expr, amber)
                value: <'hello'> (leaf, emerald)
        """
        self.assert_dump(vardef, expected)
