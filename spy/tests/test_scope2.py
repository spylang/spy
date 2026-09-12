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
        slot_name: Any = MISSING,
        level: int = 0,
        impref: Any = MISSING,
        storage: VarStorage = "direct",
    ):
        self.src_name = name
        # slot_name defaults to src_name (the common case)
        self.slot_name = name if slot_name is MISSING else slot_name
        self.varkind = varkind
        self.varkind_origin = varkind_origin
        self.level = level
        self.impref = impref
        self.storage = storage

    def __eq__(self, sym: object) -> bool:
        if not isinstance(sym, Symbol):
            return NotImplemented
        return (
            self.src_name == sym.src_name
            and self.slot_name == sym.slot_name
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
        sa = ScopeAnalyzer("test", self.mod)
        sa.analyze()
        return sa

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
        sa = self.analyze(src)
        funcdef = self.mod.get_funcdef("foo")

        # decls is about lexical scope, symtable is about the runtime frame. In this
        # case foo doesn't contain any nested block so they are the same

        # get_flattened_decls is keyed by src_name (it's a lexical/Scope view),
        # but each symbol carries its mangled slot_name.
        decls = sa.get_flattened_decls(funcdef)
        assert decls == {
            "a": MatchSymbol("a", "var", "explicit", slot_name="a$0"),
            "b": MatchSymbol("b", "const", "explicit", slot_name="b$0"),
            "c": MatchSymbol("c", "var", "explicit", slot_name="c$0"),
            "d": MatchSymbol("d", "const", "explicit", slot_name="d$0"),
            "e": MatchSymbol("e", "var", "explicit", slot_name="e$0"),
            "f": MatchSymbol("f", "var", "explicit", slot_name="f$0"),
            "g": MatchSymbol("g", "var", "explicit", slot_name="g$0"),
            "@return": MatchSymbol("@return", "var", "auto"),
        }

        # the symtable is the runtime frame: keyed by slot_name.
        symtable = sa.get_symtable(funcdef)
        assert symtable._symbols == {
            "a$0": MatchSymbol("a", "var", "explicit", slot_name="a$0"),
            "b$0": MatchSymbol("b", "const", "explicit", slot_name="b$0"),
            "c$0": MatchSymbol("c", "var", "explicit", slot_name="c$0"),
            "d$0": MatchSymbol("d", "const", "explicit", slot_name="d$0"),
            "e$0": MatchSymbol("e", "var", "explicit", slot_name="e$0"),
            "f$0": MatchSymbol("f", "var", "explicit", slot_name="f$0"),
            "g$0": MatchSymbol("g", "var", "explicit", slot_name="g$0"),
            "@return": MatchSymbol("@return", "var", "auto"),
        }

    def test_decl_use_before(self):
        src = """
        from __spy__ import strict_scoping

        def foo() -> None:
            x
            var x: i32 = 1
        """
        sa = self.analyze(src)
        funcdef = self.mod.get_funcdef("foo")
        symtable = sa.get_symtable(funcdef)
        assert symtable._symbols == {
            "x$0": MatchSymbol("x", "var", "explicit", slot_name="x$0"),
            "@return": MatchSymbol("@return", "var", "auto"),
        }

        # The use-before-declaration is recorded lazily as an UnboundLocalError
        name_node = funcdef.find(ast.Name, "x")
        assert sa.get_resolved_sym(name_node) == MatchSymbol(
            "x", "var", "explicit", slot_name="x$0", storage="UnboundLocalError"
        )

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
        sa = self.analyze(src)
        funcdef = self.mod.get_funcdef("foo")
        symtable = sa.get_symtable(funcdef)
        assert symtable._symbols == {
            "@return": MatchSymbol("@return", "var", "auto"),
        }

        nope_node = funcdef.find(ast.Name, "nope")
        assert sa.get_resolved_sym(nope_node) == MatchSymbol(
            "nope", "var", "auto", storage="NameError", level=-1
        )

    def test_scope_block_if(self):
        # [scope.block]: a name declared inside an if body is not visible outside
        sa = self.analyze("""
        from __spy__ import strict_scoping

        def foo(cond: bool) -> None:
            if cond:
                const x: i32 = 1
            x
        """)
        funcdef = self.mod.get_funcdef("foo")

        # get_flattened_decls is keyed by src_name (lexical view)
        decls = sa.get_flattened_decls(funcdef)
        assert decls == {
            "cond": MatchSymbol("cond", "var", "red-param", slot_name="cond$0"),
            "@return": MatchSymbol("@return", "var", "auto"),
            "if.then::x": MatchSymbol("x", "const", "explicit", slot_name="x$0"),
        }

        # the runtime symtable contains all locals, including block-locals like x,
        # keyed by slot_name
        symtable = sa.get_symtable(funcdef)
        assert symtable._symbols == {
            "cond$0": MatchSymbol("cond", "var", "red-param", slot_name="cond$0"),
            "@return": MatchSymbol("@return", "var", "auto"),
            "x$0": MatchSymbol("x", "const", "explicit", slot_name="x$0"),
        }

        # but the Name node for `x` is in foo_scope, so it's a NameError
        x_node = funcdef.find(ast.Name, "x")
        assert sa.get_resolved_sym(x_node) == MatchSymbol(
            "x", "var", "auto", storage="NameError", level=-1
        )

    def test_captures(self):
        src = """
        from __spy__ import strict_scoping

        const K: i32 = 42

        def foo(cond: bool) -> i32:
            var x: i32 = K
            if cond:
                var y: i32 = K
            return x
        """
        sa = self.analyze(src)
        funcdef = self.mod.get_funcdef("foo")

        captures = sa.get_all_captures(funcdef)
        # K lives in the module scope: level=1 (one frame hop).
        # i32 is a builtin: level=2 (module hop + builtins hop).
        # `bool` (the cond param type) is NOT captured: it resolves in the module
        # scope, not inside foo, even though it lives syntactically under foo.
        # Captures are keyed by the scope path of the use site.
        assert captures == {
            "K": MatchSymbol("K", "const", "explicit", level=1),
            "i32": MatchSymbol("i32", "const", "explicit", level=2),
            "if.then::K": MatchSymbol("K", "const", "explicit", level=1),
            "if.then::i32": MatchSymbol("i32", "const", "explicit", level=2),
        }
