import textwrap
from typing import Any

import pytest

from spy import ast
from spy.analyze.scope2 import ScopeAnalyzer
from spy.analyze.symtable import (
    ImportRef,
    Symbol,
    VarKind,
    VarKindOrigin,
    VarStorage,
)
from spy.parser import Parser
from spy.tests.support import MatchAnnotation, expect_errors

MISSING = object()


class MatchSymbol:
    """
    Helper class which compares equals to Symbol if the specified fields match
    """

    def __init__(
        self,
        name: str,
        varkind: VarKind,
        varkind_origin: VarKindOrigin,
        *,
        level: int = 0,
        impref: Any = MISSING,
        storage: VarStorage = "direct",
    ):
        self.name = name
        self.varkind = varkind
        self.varkind_origin = varkind_origin
        self.level = level
        self.impref = impref
        self.storage = storage

    def __eq__(self, sym: object) -> bool:
        if not isinstance(sym, Symbol):
            return NotImplemented
        return (
            self.name == sym.name
            and self.varkind == sym.varkind
            and self.varkind_origin == sym.varkind_origin
            and self.level == sym.level
            and self.storage == sym.storage
            and (self.impref is MISSING or self.impref == sym.impref)
        )


@pytest.mark.usefixtures("init")
class TestScopeAnalyzer2:
    @pytest.fixture
    def init(self, tmpdir):
        self.tmpdir = tmpdir

    def analyze(self, src: str):
        f = self.tmpdir.join("test.spy")
        src = textwrap.dedent(src)
        f.write(src)
        parser = Parser(src, str(f))
        self.mod = parser.parse()
        scopes = ScopeAnalyzer("test", self.mod)
        scopes.analyze()
        return scopes

    def expect_errors(self, src: str, main: str, *anns: MatchAnnotation):
        with expect_errors(main, *anns):
            self.analyze(src)

    def test_decl_forms(self):
        """
        [decl.forms]: var and const declarations inside a function
        """
        src = """
        from __spy__ import strict_scoping

        def foo() -> None:
            var a: i32 = 42
            const b: i32 = 43
            var c: i32
            const d: i32
            var e: auto = 44
            var f = 45
            var g: auto
        """
        scopes = self.analyze(src)
        funcdef = self.mod.get_funcdef("foo")
        scope = scopes.by_funcdef(funcdef)
        assert scope._symbols == {
            "a": MatchSymbol("a", "var", "explicit"),
            "b": MatchSymbol("b", "const", "explicit"),
            "c": MatchSymbol("c", "var", "explicit"),
            "d": MatchSymbol("d", "const", "explicit"),
            "e": MatchSymbol("e", "var", "explicit"),
            "f": MatchSymbol("f", "var", "explicit"),
            "g": MatchSymbol("g", "var", "explicit"),
            "@return": MatchSymbol("@return", "var", "auto"),
            # captured builtins
            "i32": MatchSymbol("i32", "const", "explicit", level=2),
        }

    def test_decl_use_before(self):
        src = """
        from __spy__ import strict_scoping

        def foo() -> None:
            x
            var x: i32 = 1
        """
        scopes = self.analyze(src)
        funcdef = self.mod.get_funcdef("foo")
        # The use-before-declaration is recorded lazily in node_to_sym
        name_node = funcdef.find(ast.Name, "x")
        sym = scopes.node_to_sym[name_node]
        assert sym.storage == "UnboundLocalError"

    def test_decl_no_redeclare(self):
        """
        [decl.no-redeclare]: declaring the same name twice in the same scope is an error
        """
        src = """
        from __spy__ import strict_scoping

        def foo() -> None:
            var x: i32 = 0
            var x: i32 = 1
        """
        self.expect_errors(
            src,
            "variable `x` already declared",
            ("this is the new declaration", "var x: i32 = 1"),
            ("this is the previous declaration", "var x: i32 = 0"),
        )

    def test_NameError(self):
        src = """
        from __spy__ import strict_scoping

        def foo() -> None:
            nope
        """
        scopes = self.analyze(src)
        funcdef = self.mod.get_funcdef("foo")
        symtable = scopes.by_funcdef(funcdef)
        assert symtable._symbols == {
            "@return": MatchSymbol("@return", "var", "auto"),
        }
        nope_node = funcdef.find(ast.Name, "nope")
        assert scopes.node_to_sym[nope_node] == MatchSymbol(
            "nope", "var", "auto", storage="NameError", level=-1
        )

    def test_scope_block_if(self):
        # [scope.block]: a name declared inside an if body is not visible outside
        scopes = self.analyze("""
        from __spy__ import strict_scoping

        def foo(cond: bool) -> None:
            if cond:
                const x: i32 = 1
            x
        """)
        funcdef = self.mod.get_funcdef("foo")
        ifstmt = funcdef.find(ast.If)

        # then-scope: holds only the block-local declaration
        then_scope = scopes.scopes[ifstmt, "then"]
        assert then_scope._symbols == {
            "x": MatchSymbol("x", "const", "explicit"),
        }

        # else-scope: empty (no declarations)
        else_scope = scopes.scopes[ifstmt, "else"]
        assert else_scope._symbols == {}

        # runtime symtable: x is present as a slot (registered during bind),
        # plus args, @return, and outer captures resolved during resolve
        symtable = scopes.by_funcdef(funcdef)
        assert symtable._symbols == {
            "cond": MatchSymbol("cond", "var", "red-param"),
            "@return": MatchSymbol("@return", "var", "auto"),
            "x": MatchSymbol("x", "const", "explicit"),
            "i32": MatchSymbol("i32", "const", "explicit", level=3),
        }

        # the Name node for `x` outside the if resolves as NameError
        x_node = funcdef.find(ast.Name, "x")
        assert scopes.node_to_sym[x_node] == MatchSymbol(
            "x", "var", "auto", storage="NameError", level=-1
        )
