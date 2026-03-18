"""
Test the HTML/UI behavior of the 'html' backend, which uses spyast.js
"""

import json
import shlex
import subprocess
import textwrap
from typing import Any

import pytest

from spy.backend.html import HTMLBackend
from spy.parser import Parser


def _truncate(s: str, max_len: int = 200) -> str:
    if len(s) <= max_len:
        return s
    head = max_len // 2
    tail = max_len // 2
    return f"{s[:head]} [...] {s[-tail:]}"


class Rodney:
    _flag: str
    _env: dict[str, str] | None

    def __init__(self, rodney_home: str = "local", verbose: bool = True) -> None:
        self.verbose = verbose
        if rodney_home == "local":
            self._flag = "--local"
            self._env = None
        elif rodney_home == "global":
            self._flag = "--global"
            self._env = None
        else:
            self._flag = None
            self._env = {"RODNEY_HOME": rodney_home}

        if self.verbose:
            print()
            if self._env:
                print(f"$ export RODNEY_HOME={rodney_home}")

    def __call__(self, *args: str) -> str:
        cmd = ["rodney"]
        if self._flag:
            cmd.append(self._flag)
        cmd.extend(args)
        if self.verbose:
            print(f"$ {shlex.join(cmd)}")
        result = subprocess.run(
            cmd,
            env={**subprocess.os.environ, **self._env} if self._env else None,
            capture_output=True,
            text=True,
        )
        if self.verbose:
            if result.stdout.strip():
                print(f"-> {_truncate(result.stdout.strip())}")
            if result.stderr.strip():
                print(f"!! {_truncate(result.stderr.strip())}")
        if result.returncode not in (0, 1):
            raise RuntimeError(f"rodney {' '.join(args)} failed:\n{result.stderr}")
        return result.stdout.strip()


@pytest.mark.usefixtures("init")
class TestSPyAST_js:
    @pytest.fixture(scope="class")
    def _rodney(self, tmp_path_factory):
        rodney_home = str(tmp_path_factory.mktemp("rodney"))
        rodney = Rodney(rodney_home=rodney_home)
        rodney("start")
        yield rodney
        rodney("stop")

    @pytest.fixture
    def init(self, tmpdir, _rodney):
        self.tmpdir = tmpdir
        self.rodney = _rodney

    def generate_html(self, src: str) -> str:
        src = textwrap.dedent(src)
        f = self.tmpdir.join("test.spy")
        f.write(src)
        parser = Parser(src, str(f))
        mod = parser.parse()
        b = HTMLBackend(spyast_js="inline")
        html = b.generate([("test", mod)])
        out = self.tmpdir.join("test.html")
        out.write(html)
        return str(out)

    def open(self, path: str) -> None:
        self.rodney("open", f"file://{path}")
        self.rodney("waitstable")

    def js(self, expr: str) -> str:
        return self.rodney("js", expr)

    def count(self, selector: str) -> int:
        return int(self.rodney("count", selector))

    def get_nodes(self) -> list[dict[str, Any]]:
        # Each <g> has a _nd property set by spyast.js with the node data
        raw = self.js(
            "JSON.stringify([...document.querySelectorAll('svg g[style]')]"
            ".filter(g => g._nd).map(g => {"
            "  const nd = g._nd;"
            "  const text = g.querySelector('text');"
            "  return {"
            "    label: nd.label,"
            "    src: nd.src || null,"
            "    isCollapsed: nd.isCollapsed,"
            "    hasChildren: nd.hasChildren,"
            "    text: text ? text.textContent : null"
            "  };"
            "}))"
        )
        return json.loads(raw)

    def get_node(self, label: str) -> dict[str, Any]:
        for node in self.get_nodes():
            if node["label"] == label:
                return node
        raise KeyError(f"node with label {label!r} not found")

    def get_visible_labels(self) -> set[str]:
        return {n["label"] for n in self.get_nodes()}

    def right_click_node(self, text: str) -> None:
        # Find the <g> element via its _nd label rather than text content,
        # since text content changes when collapsed/expanded
        self.js(
            f"[...document.querySelectorAll('svg g[style]')]"
            f".find(g => g._nd && g._nd.label === {text!r})"
            f".dispatchEvent("
            f"new MouseEvent('contextmenu', {{bubbles: true, clientX: 100, clientY: 100}}))"
        )
        self.rodney("waitstable")

    def click_node(self, text: str) -> None:
        self.js(
            f"[...document.querySelectorAll('svg g > text')]"
            f".find(t => t.textContent === {text!r})"
            f".parentElement.dispatchEvent("
            f"new MouseEvent('click', {{bubbles: true}}))"
        )
        self.rodney("waitstable")
        self.rodney("sleep", "0.5")

    def click_node_by_label(self, label: str) -> None:
        self.js(
            f"[...document.querySelectorAll('svg g[style]')]"
            f".find(g => g._nd && g._nd.label === {label!r})"
            f".dispatchEvent("
            f"new MouseEvent('click', {{bubbles: true}}))"
        )
        self.rodney("waitstable")
        self.rodney("sleep", "0.5")

    def test_expand_collapse(self):
        path = self.generate_html("""
        def foo(x: i32) -> i32:
            return x + 1
        """)
        self.open(path)

        # --- initial state: FuncDef expanded, Return collapsed ---
        funcdef = self.get_node("FuncDef: red foo")
        assert funcdef["isCollapsed"] is False
        assert funcdef["text"] == "FuncDef: red foo"

        ret = self.get_node("Return")
        assert ret["isCollapsed"] is True
        assert ret["text"] == "return x + 1"

        # expanded FuncDef shows its children
        visible = self.get_visible_labels()
        assert "Return" in visible
        assert "FuncArg: x simple" in visible
        # collapsed Return hides its children
        assert "BinOp: +" not in visible

        # --- collapse FuncDef: children disappear, shows source ---
        self.click_node("FuncDef: red foo")

        funcdef = self.get_node("FuncDef: red foo")
        assert funcdef["isCollapsed"] is True
        assert funcdef["text"] != "FuncDef: red foo"
        visible = self.get_visible_labels()
        assert "Return" not in visible
        assert "FuncArg: x simple" not in visible

        # --- re-expand FuncDef: children come back ---
        self.click_node(funcdef["text"])

        funcdef = self.get_node("FuncDef: red foo")
        assert funcdef["isCollapsed"] is False
        assert funcdef["text"] == "FuncDef: red foo"
        visible = self.get_visible_labels()
        assert "Return" in visible
        assert "FuncArg: x simple" in visible

        # --- expand Return: its children appear ---
        ret = self.get_node("Return")
        self.click_node(ret["text"])

        ret = self.get_node("Return")
        assert ret["isCollapsed"] is False
        assert ret["text"] == "Return"
        assert "BinOp: +" in self.get_visible_labels()

    def test_focus_subtree(self):
        path = self.generate_html("""\
        def foo(x: i32) -> i32:
            return x + 1

        def bar(y: i32) -> i32:
            return y - 1
        """)
        self.open(path)

        # Initially both FuncDefs are visible
        visible = self.get_visible_labels()
        assert "FuncDef: red foo" in visible
        assert "FuncDef: red bar" in visible

        # Right-click on FuncDef: red foo and click "Focus on this subtree"
        self.right_click_node("FuncDef: red foo")
        menu_text = self.js(
            "document.getElementById('spyast-context-menu')?.textContent || ''"
        )
        assert "Focus on this subtree" in menu_text

        self.js(
            "[...document.getElementById('spyast-context-menu').children]"
            ".find(d => d.textContent === 'Focus on this subtree')"
            ".dispatchEvent(new MouseEvent('click', {bubbles: true}))"
        )
        self.rodney("waitstable")
        self.rodney("sleep", "0.5")

        # Now only the FuncDef: red foo subtree is visible
        visible = self.get_visible_labels()
        assert "FuncDef: red foo" in visible
        assert "FuncDef: red bar" not in visible

        # The "Show all" banner should be visible
        banner = self.js(
            "document.getElementById('spyast-show-all-banner')?.style.display"
        )
        assert banner != "none"

        # The URL hash should contain focus info
        url_hash = self.js("location.hash")
        assert "focus:" in url_hash

        # Click "Show all" to restore
        self.js(
            "document.querySelector('#spyast-show-all-banner button')"
            ".dispatchEvent(new MouseEvent('click', {bubbles: true}))"
        )
        self.rodney("waitstable")
        self.rodney("sleep", "0.5")

        # Both FuncDefs visible again
        visible = self.get_visible_labels()
        assert "FuncDef: red foo" in visible
        assert "FuncDef: red bar" in visible

        # Banner hidden
        banner = self.js(
            "document.getElementById('spyast-show-all-banner')?.style.display"
        )
        assert banner == "none"

    def test_export_svg(self):
        path = self.generate_html("""\
        def foo(x: i32) -> i32:
            return x + 1
        """)
        self.open(path)

        # Export the Module (root) subtree — Return node starts collapsed
        svg_collapsed = self.js("SPyAstViz._instances[0].exportSubtreeSVG(0)")
        assert svg_collapsed.startswith("<?xml version")
        assert 'xmlns="http://www.w3.org/2000/svg"' in svg_collapsed
        # Should not contain inline position styles (cleaned up for static SVG)
        assert "position:" not in svg_collapsed
        # Should use transform attribute instead of CSS transform
        assert 'transform="translate(' in svg_collapsed
        # Return starts collapsed, so the SVG should show the source text
        assert "return x + 1" in svg_collapsed
        # BinOp is a child of Return; collapsed means it's NOT rendered
        assert "BinOp" not in svg_collapsed

        # Now expand the Return node and export again
        self.click_node("return x + 1")
        svg_expanded = self.js("SPyAstViz._instances[0].exportSubtreeSVG(0)")
        # Return is now expanded: the label "Return" should appear (not source text),
        # and its child (BinOp, collapsed, showing "x + 1") should be rendered
        assert ">Return<" in svg_expanded
        # The "value" edge label connects Return to its child
        assert ">value<" in svg_expanded

        # Right-click should show SVG export options
        self.right_click_node("FuncDef: red foo")
        menu_text = self.js(
            "document.getElementById('spyast-context-menu')?.textContent || ''"
        )
        assert "Copy SVG to clipboard" in menu_text
        assert "Save SVG as file" in menu_text

    def test_hide_leaves(self):
        path = self.generate_html("""\
        def foo(x: i32) -> i32:
            return x + 1
        """)
        self.open(path)

        # FuncDef starts expanded so leaf children are visible
        visible = self.get_visible_labels()
        assert "'red'" in visible

        # Right-click and hide leaves
        self.right_click_node("FuncDef: red foo")
        menu_text = self.js(
            "document.getElementById('spyast-context-menu')?.textContent || ''"
        )
        assert "Hide leaves" in menu_text
        self.js(
            "[...document.getElementById('spyast-context-menu').children]"
            ".find(d => d.textContent === 'Hide leaves')"
            ".dispatchEvent(new MouseEvent('click', {bubbles: true}))"
        )
        self.rodney("waitstable")
        self.rodney("sleep", "0.5")

        # Now leaves should be hidden
        visible = self.get_visible_labels()
        assert "'red'" not in visible
        # But non-leaf nodes should still be visible
        assert "FuncDef: red foo" in visible

        # Hash should contain 'noleaves'
        url_hash = self.js("location.hash")
        assert "noleaves" in url_hash

        # Right-click again — menu should say "Show leaves"
        self.right_click_node("FuncDef: red foo")
        menu_text = self.js(
            "document.getElementById('spyast-context-menu')?.textContent || ''"
        )
        assert "Show leaves" in menu_text
        self.js(
            "[...document.getElementById('spyast-context-menu').children]"
            ".find(d => d.textContent === 'Show leaves')"
            ".dispatchEvent(new MouseEvent('click', {bubbles: true}))"
        )
        self.rodney("waitstable")
        self.rodney("sleep", "0.5")

        # Leaves should be visible again
        visible = self.get_visible_labels()
        assert "'red'" in visible

        # Hash should not contain 'noleaves'
        url_hash = self.js("location.hash")
        assert "noleaves" not in url_hash
