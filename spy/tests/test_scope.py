import textwrap
from typing import Any

import pytest

from spy import ast
from spy.analyze.scope import ScopeAnalyzer
from spy.analyze.symtable import (
    Color,
    ImportRef,
    Symbol,
    SymTable,
    VarKind,
    VarKindOrigin,
    VarStorage,
)
from spy.fqn import FQN
from spy.parser import Parser
from spy.tests.support import MatchAnnotation, expect_errors
from spy.vm.vm import SPyVM

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
class TestScopeAnalyzer:
    @pytest.fixture
    def init(self, tmpdir):
        self.vm = SPyVM()
        self.tmpdir = tmpdir

    def analyze(self, src: str):
        f = self.tmpdir.join("test.spy")
        src = textwrap.dedent(src)
        f.write(src)
        parser = Parser(src, str(f))
        self.mod = parser.parse()
        scopes = ScopeAnalyzer(self.vm, "test", self.mod)
        scopes.analyze()
        return scopes

    def expect_errors(self, src: str, main: str, *anns: MatchAnnotation):
        with expect_errors(main, *anns):
            self.analyze(src)

    def test_global(self):
        scopes = self.analyze("""
        a = 0
        b: i32 = 0
        const c: i32 = 0
        var d: i32 = 0

        def foo() -> None:
            pass

        def bar() -> None:
            pass
        """)
        scope = scopes.by_module()
        assert scope.name == "test"
        assert scope.color == "blue"
        assert scope._symbols == {
            "a": MatchSymbol("a", "const", "global-const"),
            "b": MatchSymbol("b", "const", "global-const"),
            "c": MatchSymbol("c", "const", "explicit"),
            "d": MatchSymbol("d", "var", "explicit", storage="cell"),
            "foo": MatchSymbol("foo", "const", "funcdef"),
            "bar": MatchSymbol("bar", "const", "funcdef"),
            # captured
            "i32": MatchSymbol("i32", "const", "explicit", level=1),
        }

    def test_funcargs_and_locals(self):
        scopes = self.analyze("""
        def foo(a: i32) -> i32:
            b = 0
            c: i32 = 0
            const d: i32 = 0
            var e: i32 = 0
        """)
        funcdef = self.mod.get_funcdef("foo")
        scope = scopes.by_funcdef(funcdef)
        assert scope.name == "test::foo"
        assert scope.color == "red"
        assert scope._symbols == {
            "a": MatchSymbol("a", "var", "red-param"),
            "b": MatchSymbol("b", "const", "auto"),
            "c": MatchSymbol("c", "const", "auto"),
            "d": MatchSymbol("d", "const", "explicit"),
            "e": MatchSymbol("e", "var", "explicit"),
            "@return": MatchSymbol("@return", "var", "auto"),
            # captured
            "i32": MatchSymbol("i32", "const", "explicit", level=2),
        }
        assert funcdef.symtable is scope

    def test_var_and_const(self):
        scopes = self.analyze("""
        def range(n: i32) -> dynamic:
            pass

        def foo(a: i32) -> None:
            # a is not touched   # param: var
            b: i32 = 0           # vardef, implicit varkind: const
            var c: i32 = 0       # vardef, explicit varkind: var
            d = 0                # single assign: const
            e = 0                # multi assign: var
            e = 0
            f = 0                # single assign + augassign: var
            f += 0
            g: i32 = 0           # vardef + augassign: var
            g += 0

            for i in range(10):  # loop variable: var
                h = 0            # assign in loop: var

            while True:
                j = 0       # assign in loop: var
        """)
        funcdef = self.mod.get_funcdef("foo")
        scope = scopes.by_funcdef(funcdef)
        assert scope.name == "test::foo"
        assert scope.color == "red"
        assert scope._symbols == {
            "a": MatchSymbol("a", "var", "red-param"),
            "b": MatchSymbol("b", "const", "auto"),
            "c": MatchSymbol("c", "var", "explicit"),
            "d": MatchSymbol("d", "const", "auto"),
            "e": MatchSymbol("e", "var", "auto"),
            "f": MatchSymbol("f", "var", "auto"),
            "g": MatchSymbol("g", "var", "auto"),
            "h": MatchSymbol("h", "var", "auto"),
            "i": MatchSymbol("i", "var", "auto"),
            "j": MatchSymbol("j", "var", "auto"),
            #
            "_$iter0": MatchSymbol("_$iter0", "var", "auto"),
            "@return": MatchSymbol("@return", "var", "auto"),
            "range": MatchSymbol("range", "const", "funcdef", level=1),
            "i32": MatchSymbol("i32", "const", "explicit", level=2),
        }

    def test_assignexpr_scope(self):
        scopes = self.analyze("""
        def foo() -> i32:
            if (x := 1):
                pass
            return x

        def bar() -> None:
            while True:
                if (y := 1):
                    break
        """)
        foo_scope = scopes.by_funcdef(self.mod.get_funcdef("foo"))
        assert foo_scope._symbols == {
            "x": MatchSymbol("x", "const", "auto"),
            "@return": MatchSymbol("@return", "var", "auto"),
        }
        bar_scope = scopes.by_funcdef(self.mod.get_funcdef("bar"))
        assert bar_scope._symbols == {
            "y": MatchSymbol("y", "var", "auto"),
            "@return": MatchSymbol("@return", "var", "auto"),
        }

    def test_assignexpr_loop_tests_are_var(self):
        scopes = self.analyze("""
        def foo() -> None:
            while (x := 1):
                break
            for _ in (xs := [1]):
                pass
        """)

        foo_scope = scopes.by_funcdef(self.mod.get_funcdef("foo"))
        assert foo_scope._symbols["x"] == MatchSymbol("x", "var", "auto")
        assert foo_scope._symbols["xs"] == MatchSymbol("xs", "var", "auto")

    def test_assignexpr_globals(self):
        scopes = self.analyze("""
        x = 1
        var y: i32 = 1

        def main() -> None:
            z0 = (x := 1) # scope captures const x; runtime should reject assigning to it
            z1 = (y := 1)
        """)
        scope = scopes.by_funcdef(self.mod.get_funcdef("main"))
        assert scope._symbols == {
            "x": MatchSymbol("x", "const", "global-const", level=1),
            "y": MatchSymbol("y", "var", "explicit", level=1, storage="cell"),
            "z0": MatchSymbol("z0", "const", "auto"),
            "z1": MatchSymbol("z1", "const", "auto"),
            "@return": MatchSymbol("@return", "var", "auto"),
        }

    def test_var_and_const_assignexpr(self):
        scopes = self.analyze("""
        def foo() -> None:
            a = (x := 0)
            b = (x := 1)
            if True:
                c = (y := 2)
            while True:
                d = (z := 3)
                break
        """)
        scope = scopes.by_funcdef(self.mod.get_funcdef("foo"))
        assert scope._symbols == {
            "a": MatchSymbol("a", "const", "auto"),
            "b": MatchSymbol("b", "const", "auto"),
            "c": MatchSymbol("c", "const", "auto"),
            "d": MatchSymbol("d", "var", "auto"),
            "x": MatchSymbol("x", "var", "auto"),
            "y": MatchSymbol("y", "const", "auto"),
            "z": MatchSymbol("z", "var", "auto"),
            "@return": MatchSymbol("@return", "var", "auto"),
        }

    def test_vardef_initializer_declares_assignexpr_target(self):
        scopes = self.analyze("""
        def foo() -> i32:
            var z: i32 = (x := 1)
            return x + z
        """)
        scope = scopes.by_funcdef(self.mod.get_funcdef("foo"))
        assert scope._symbols == {
            "z": MatchSymbol("z", "var", "explicit"),
            "x": MatchSymbol("x", "const", "auto"),
            "@return": MatchSymbol("@return", "var", "auto"),
            "i32": MatchSymbol("i32", "const", "explicit", level=2),
        }

    def test_const_var_without_type(self):
        scopes = self.analyze("""
        def foo() -> None:
            var x = 42
            const y = 100
            x = 50
        """)
        funcdef = self.mod.get_funcdef("foo")
        scope = scopes.by_funcdef(funcdef)
        assert scope.name == "test::foo"
        assert scope.color == "red"
        assert scope._symbols == {
            "x": MatchSymbol("x", "var", "explicit"),
            "y": MatchSymbol("y", "const", "explicit"),
            "@return": MatchSymbol("@return", "var", "auto"),
        }

    def test_blue_func(self):
        scopes = self.analyze("""
        @blue
        def foo(x) -> None:
            pass
        """)
        funcdef = self.mod.get_funcdef("foo")
        scope = scopes.by_funcdef(funcdef)
        assert scope.name == "test::foo"
        assert scope.color == "blue"
        assert scope._symbols == {
            "x": MatchSymbol("x", "const", "blue-param"),
            "@return": MatchSymbol("@return", "var", "auto"),
        }

    def test_blue_param_stay_const(self):
        # this code will raise when executed, see
        # test_basic.py:test_cannot_assign_to_blue_param. But here we want to test that
        # "const" of "blue-param" origin cannot be promoted to "var"
        scopes = self.analyze("""
        @blue
        def foo(x) -> None:
            x = 4
        """)
        funcdef = self.mod.get_funcdef("foo")
        scope = scopes.by_funcdef(funcdef)
        assert scope._symbols == {
            "x": MatchSymbol("x", "const", "blue-param"),
            "@return": MatchSymbol("@return", "var", "auto"),
        }

    def test_assign_does_not_redeclare(self):
        scopes = self.analyze("""
        def foo() -> None:
            x: i32 = 0
            x = 1
        """)
        funcdef = self.mod.get_funcdef("foo")
        scope = scopes.by_funcdef(funcdef)
        assert scope._symbols == {
            "x": MatchSymbol("x", "var", "auto"),
            "@return": MatchSymbol("@return", "var", "auto"),
            "i32": MatchSymbol("i32", "const", "explicit", level=2),
        }

    def test_red_cannot_redeclare(self):
        # see also the equivalent test
        # TestBasic.test_blue_cannot_redeclare
        src = """
        def foo() -> i32:
            x: i32 = 1
            x: i32 = 2
        """
        self.expect_errors(
            src,
            "variable `x` already declared",
            ("this is the new declaration", "x: i32 = 2"),
            ("this is the previous declaration", "x: i32 = 1"),
        )

    def test_blue_can_redeclare(self):
        # see also the related test
        # TestBasic.test_blue_cannot_redeclare

        # The difference is that at ScopeAnalyzer time, we allow POTENTIAL
        # multiple declarations inside @blue functions, but if we actually
        # redeclare it, we catch it at runtime.
        src = """
        @blue
        def foo(FLAG):
            if FLAG:
                x = 1
            else:
                x = 'hello'
        """
        scopes = self.analyze(src)
        funcdef = self.mod.get_funcdef("foo")
        scope = scopes.by_funcdef(funcdef)
        assert scope._symbols == {
            "FLAG": MatchSymbol("FLAG", "const", "blue-param"),
            "x": MatchSymbol("x", "var", "auto"),
            "@return": MatchSymbol("@return", "var", "auto"),
        }

    def test_no_shadowing(self):
        src = """
        x: i32 = 1
        def foo() -> i32:
            x: i32 = 2
        """
        self.expect_errors(
            src,
            "variable `x` shadows a name declared in an outer scope",
            ("this is the new declaration", "x: i32 = 2"),
            ("this is the previous declaration", "x: i32 = 1"),
        )

    def test_can_shadow_builtins(self):
        scopes = self.analyze("""
        # Shadow the builtin i32 at module level
        i32: type = str

        def foo() -> None:
            # Shadow the builtin str inside a function
            str: type = i32
        """)

        # Check module scope
        mod_scope = scopes.by_module()
        assert mod_scope._symbols == {
            "i32": MatchSymbol("i32", "const", "global-const"),
            "foo": MatchSymbol("foo", "const", "funcdef"),
            # captured builtins that are referenced
            "type": MatchSymbol("type", "const", "explicit", level=1),
            "str": MatchSymbol("str", "const", "explicit", level=1),
        }

        # Check function scope
        funcdef = self.mod.get_funcdef("foo")
        func_scope = scopes.by_funcdef(funcdef)
        assert func_scope._symbols == {
            "str": MatchSymbol("str", "const", "auto"),
            "@return": MatchSymbol("@return", "var", "auto"),
            "i32": MatchSymbol("i32", "const", "global-const", level=1),
            "type": MatchSymbol("type", "const", "explicit", level=2),
        }

    def test_inner_funcdef(self):
        scopes = self.analyze("""
        def foo() -> None:
            x: i32 = 0
            def bar(y: i32) -> i32:
                return x + y
        """)
        foodef = self.mod.get_funcdef("foo")
        assert foodef.symtable._symbols == {
            "x": MatchSymbol("x", "const", "auto"),
            "bar": MatchSymbol("bar", "const", "funcdef"),
            "@return": MatchSymbol("@return", "var", "auto"),
            "i32": MatchSymbol("i32", "const", "explicit", level=2),
        }
        #
        bardef = foodef.body[1]
        assert isinstance(bardef, ast.FuncDef)
        assert bardef.symtable._symbols == {
            "y": MatchSymbol("y", "var", "red-param"),
            "@return": MatchSymbol("@return", "var", "auto"),
            "x": MatchSymbol("x", "const", "auto", level=1),
        }

    def test_import(self):
        scopes = self.analyze("""
        import foo
        from bar import aaa
        from baz import bbb as ccc
        """)
        scope = scopes.by_module()
        assert scope._symbols == {
            "foo": MatchSymbol("foo", "const", "auto", impref=ImportRef("foo", None)),
            "aaa": MatchSymbol("aaa", "const", "auto", impref=ImportRef("bar", "aaa")),
            "ccc": MatchSymbol("ccc", "const", "auto", impref=ImportRef("baz", "bbb")),
        }

    def test_class(self):
        scopes = self.analyze("""
        class Foo:
            x: i32
            y: i32

            def foo() -> None:
                pass
        """)
        mod_scope = scopes.by_module()
        assert mod_scope._symbols == {
            "Foo": MatchSymbol("Foo", "const", "classdef"),
        }
        classdef = self.mod.get_classdef("Foo")
        assert classdef.symtable._symbols == {
            "x": MatchSymbol("x", "var", "class-field"),
            "y": MatchSymbol("y", "var", "class-field"),
            "foo": MatchSymbol("foo", "const", "funcdef"),
            "i32": MatchSymbol("i32", "const", "explicit", level=2),
        }

    def test_vararg(self):
        scopes = self.analyze("""
        def foo(a: i32, *args: str) -> None:
            pass
        """)
        funcdef = self.mod.get_funcdef("foo")
        scope = scopes.by_funcdef(funcdef)
        assert scope.name == "test::foo"
        assert scope.color == "red"
        assert scope._symbols == {
            "a": MatchSymbol("a", "var", "red-param"),
            "args": MatchSymbol("args", "var", "red-param"),
            "@return": MatchSymbol("@return", "var", "auto"),
        }

    def test_capture_across_multiple_scopes(self):
        # see also the similar test in test_basic
        scopes = self.analyze("""
        def a() -> dynamic:
            x = 42  # x is defined in this scope
            def b() -> dynamic:
                # x is referenced but NOT defined in this scope
                y = x
                def c() -> i32:
                    # x should point TWO levels up
                    return x
                return c
            return b

        """)

        def get_scope(name: str) -> SymTable:
            for funcdef, scope in scopes.inner_scopes.items():
                if funcdef.name == name:
                    return scope
            raise KeyError

        a = get_scope("a")
        b = get_scope("b")
        c = get_scope("c")
        assert a._symbols["x"] == MatchSymbol("x", "const", "auto", level=0)
        assert b._symbols["x"] == MatchSymbol("x", "const", "auto", level=1)
        assert c._symbols["x"] == MatchSymbol("x", "const", "auto", level=2)

    def test_capture_decorator(self):
        scopes = self.analyze("""
        @blue
        def deco(fn):
            pass

        @blue
        def outer():
            @deco
            def inner() -> None:
                pass
        """)
        funcdef = self.mod.get_funcdef("outer")
        scope = scopes.by_funcdef(funcdef)
        assert scope.name == "test::outer"
        assert scope.color == "blue"
        assert scope._symbols == {
            "inner": MatchSymbol("inner", "const", "funcdef"),
            "@return": MatchSymbol("@return", "var", "auto"),
            "deco": MatchSymbol("deco", "const", "funcdef", level=1),
        }

    def test_symbol_not_found(self):
        scopes = self.analyze("""
        def foo() -> None:
            x = y
        """)
        funcdef = self.mod.get_funcdef("foo")
        scope = scopes.by_funcdef(funcdef)
        assert scope._symbols == {
            "x": MatchSymbol("x", "const", "auto"),
            "@return": MatchSymbol("@return", "var", "auto"),
            "y": MatchSymbol("y", "var", "auto", level=-1, storage="NameError"),
        }

    def test_for_loop(self):
        scopes = self.analyze("""
        def foo() -> None:
            for i in range(10):
                x: i32 = i * 2
        """)
        funcdef = self.mod.get_funcdef("foo")
        scope = scopes.by_funcdef(funcdef)
        assert scope._symbols == {
            "_$iter0": MatchSymbol("_$iter0", "var", "auto"),
            "i": MatchSymbol("i", "var", "auto"),
            "x": MatchSymbol("x", "var", "auto"),
            "@return": MatchSymbol("@return", "var", "auto"),
            "range": MatchSymbol("range", "const", "explicit", level=2),
            "i32": MatchSymbol("i32", "const", "explicit", level=2),
        }

    def test_for_loop_multiple(self):
        scopes = self.analyze("""
        def foo() -> None:
            for i in range(10):
                x: i32 = i * 2
            for j in range(5):
                y: i32 = j * 3
        """)
        funcdef = self.mod.get_funcdef("foo")
        scope = scopes.by_funcdef(funcdef)
        assert scope._symbols == {
            "_$iter0": MatchSymbol("_$iter0", "var", "auto"),
            "_$iter1": MatchSymbol("_$iter1", "var", "auto"),
            "i": MatchSymbol("i", "var", "auto"),
            "j": MatchSymbol("j", "var", "auto"),
            "x": MatchSymbol("x", "var", "auto"),
            "y": MatchSymbol("y", "var", "auto"),
            "@return": MatchSymbol("@return", "var", "auto"),
            "range": MatchSymbol("range", "const", "explicit", level=2),
            "i32": MatchSymbol("i32", "const", "explicit", level=2),
        }

    def test_for_loop_no_shadowing(self):
        src = """
        i: i32 = 0

        def foo() -> None:
            for i in range(10):
                pass
        """
        self.expect_errors(
            src,
            "variable `i` shadows a name declared in an outer scope",
            ("this is the new declaration", "i"),
            ("this is the previous declaration", "i: i32 = 0"),
        )

    def test_global_const_hint(self):
        scopes = self.analyze("""
        x: i32 = 42
        var y: i32 = 0
        """)
        scope = scopes.by_module()
        assert scope._symbols == {
            "x": MatchSymbol("x", "const", "global-const"),
            "y": MatchSymbol("y", "var", "explicit", storage="cell"),
            "i32": MatchSymbol("i32", "const", "explicit", level=1),
        }

    def test_blue_func_vararg(self):
        scopes = self.analyze("""
        @blue
        def foo(a: i32, *args: str) -> None:
            pass
        """)
        funcdef = self.mod.get_funcdef("foo")
        scope = scopes.by_funcdef(funcdef)
        assert scope._symbols == {
            "a": MatchSymbol("a", "const", "blue-param"),
            "args": MatchSymbol("args", "const", "blue-param"),
            "@return": MatchSymbol("@return", "var", "auto"),
        }

    def test_list_literal(self):
        # using a string literal implicitly imports '_list'
        scopes = self.analyze("""
        def foo() -> None:
            [1, 2, 3]
        """)
        scope = scopes.by_module()
        assert scope.implicit_imports == {"_list"}
