import textwrap
from typing import Any

import pytest

from spy import ast
from spy.analyze.scope import ScopeAnalyzer
from spy.analyze.symtable import Color, ImportRef, Symbol, SymTable, VarKind, VarStorage
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
        level: int = 0,
        impref: Any = MISSING,
        storage: VarStorage = "direct",
        hints: Any = MISSING,
    ):
        self.name = name
        self.varkind = varkind
        self.level = level
        self.impref = impref
        self.storage = storage
        self.hints = hints

    def __eq__(self, sym: object) -> bool:
        if not isinstance(sym, Symbol):
            return NotImplemented
        return (
            self.name == sym.name
            and self.varkind == sym.varkind
            and self.level == sym.level
            and self.storage == sym.storage
            and (self.impref is MISSING or self.impref == sym.impref)
            and (self.hints is MISSING or self.hints == sym.hints)
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
        x: i32 = 0
        var y: i32 = 0

        def foo() -> None:
            pass

        def bar() -> None:
            pass
        """)
        scope = scopes.by_module()
        assert scope.name == "test"
        assert scope.color == "blue"
        assert scope._symbols == {
            "x": MatchSymbol("x", "const"),
            "y": MatchSymbol("y", "var", storage="cell"),
            "foo": MatchSymbol("foo", "const"),
            "bar": MatchSymbol("bar", "const"),
            # captured
            "i32": MatchSymbol("i32", "const", level=1),
        }

    def test_funcargs_and_locals(self):
        scopes = self.analyze("""
        def foo(x: i32) -> i32:
            y: i32 = 42
            z = 42
        """)
        funcdef = self.mod.get_funcdef("foo")
        scope = scopes.by_funcdef(funcdef)
        assert scope.name == "test::foo"
        assert scope.color == "red"
        assert scope._symbols == {
            "x": MatchSymbol("x", "const"),
            "y": MatchSymbol("y", "var"),
            "z": MatchSymbol("z", "const"),
            "@return": MatchSymbol("@return", "var"),
            # captured
            "i32": MatchSymbol("i32", "const", level=2),
        }
        assert funcdef.symtable is scope

    def test_var_and_const(self):
        scopes = self.analyze("""
        def range(n: i32) -> dynamic:
            pass

        def foo(x: i32, y: i32) -> None:
            # x is not touched   # param: const
            y = 0                # param + assign: var
            # b: i32 = 0           # vardef, implicit varkind: const   FIXME
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
                f = 0       # assign in loop: var
        """)
        funcdef = self.mod.get_funcdef("foo")
        scope = scopes.by_funcdef(funcdef)
        assert scope.name == "test::foo"
        assert scope.color == "red"
        assert scope._symbols == {
            "x": MatchSymbol("x", "const"),
            "y": MatchSymbol("y", "var"),
            # "b": MatchSymbol("b", "const"),  # FIXME
            "c": MatchSymbol("c", "var"),
            "d": MatchSymbol("d", "const"),
            "e": MatchSymbol("e", "var"),
            "f": MatchSymbol("f", "var"),
            "g": MatchSymbol("g", "var"),
            "h": MatchSymbol("h", "var"),
            "i": MatchSymbol("i", "var"),
            "f": MatchSymbol("f", "var"),
            #
            "_$iter0": MatchSymbol("_$iter0", "var"),
            "@return": MatchSymbol("@return", "var"),
            "range": MatchSymbol("range", "const", level=1),
            "i32": MatchSymbol("i32", "const", level=2),
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
            "x": MatchSymbol("x", "const", hints=("blue-param",)),
            "@return": MatchSymbol("@return", "var", hints=()),
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
            "x": MatchSymbol("x", "var"),
            "@return": MatchSymbol("@return", "var"),
            "i32": MatchSymbol("i32", "const", level=2),
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
            "FLAG": MatchSymbol("FLAG", "const"),
            "x": MatchSymbol("x", "var"),
            "@return": MatchSymbol("@return", "var"),
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

    def test_inner_funcdef(self):
        scopes = self.analyze("""
        def foo() -> None:
            x: i32 = 0
            def bar(y: i32) -> i32:
                return x + y
        """)
        foodef = self.mod.get_funcdef("foo")
        assert foodef.symtable._symbols == {
            "x": MatchSymbol("x", "var"),
            "bar": MatchSymbol("bar", "const"),
            "@return": MatchSymbol("@return", "var"),
            "i32": MatchSymbol("i32", "const", level=2),
        }
        #
        bardef = foodef.body[1]
        assert isinstance(bardef, ast.FuncDef)
        assert bardef.symtable._symbols == {
            "y": MatchSymbol("y", "const"),
            "@return": MatchSymbol("@return", "var"),
            "x": MatchSymbol("x", "var", level=1),
        }

    def test_import(self):
        scopes = self.analyze("""
        from builtins import i32 as my_int
        """)
        scope = scopes.by_module()
        assert scope._symbols == {
            "my_int": MatchSymbol(
                "my_int", "const", impref=ImportRef("builtins", "i32")
            ),
        }

    def test_import_wrong_attribute(self):
        src = "from builtins import aaa"
        self.expect_errors(
            src,
            "cannot import `builtins.aaa`",
            ("attribute `aaa` does not exist in module `builtins`", "aaa"),
        )

    def test_import_wrong_module(self):
        src = "from xxx import aaa"
        self.expect_errors(
            src,
            "cannot import `xxx.aaa`",
            ("module `xxx` does not exist", "from xxx import aaa"),
        )

    def test_import_wrong_py_module(self):
        # Create a .py file that would match the import
        py_file = self.tmpdir.join("mymodule.py")
        py_file.write("x = 42\n")

        self.vm.path.append(str(self.tmpdir))
        src = "from mymodule import x"
        self.expect_errors(
            src,
            "cannot import `mymodule.x`",
            (
                "file `mymodule.py` exists, but py files cannot be imported",
                "from mymodule import x",
            ),
        )

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
            "Foo": MatchSymbol("Foo", "const"),
        }
        classdef = self.mod.get_classdef("Foo")
        assert classdef.symtable._symbols == {
            "x": MatchSymbol("x", "var"),
            "y": MatchSymbol("y", "var"),
            "foo": MatchSymbol("foo", "const"),
            "i32": MatchSymbol("i32", "const", level=2),
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
            "a": MatchSymbol("a", "const"),
            "args": MatchSymbol("args", "const"),
            "@return": MatchSymbol("@return", "var"),
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
        assert a._symbols["x"] == MatchSymbol("x", "const", level=0)
        assert b._symbols["x"] == MatchSymbol("x", "const", level=1)
        assert c._symbols["x"] == MatchSymbol("x", "const", level=2)

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
            "inner": MatchSymbol("inner", "const"),
            "@return": MatchSymbol("@return", "var"),
            "deco": MatchSymbol("deco", "const", level=1),
        }

    def test_symbol_not_found(self):
        scopes = self.analyze("""
        def foo() -> None:
            x = y
        """)
        funcdef = self.mod.get_funcdef("foo")
        scope = scopes.by_funcdef(funcdef)
        assert scope._symbols == {
            "x": MatchSymbol("x", "const"),  # inferred const
            "@return": MatchSymbol("@return", "var"),
            "y": MatchSymbol("y", "var", level=-1, storage="NameError"),
        }

    def test_for_loop(self):
        scopes = self.analyze("""
        # XXX kill this when 'range' becomes a builtin
        def range(n: i32) -> dynamic:
            pass

        def foo() -> None:
            for i in range(10):
                x: i32 = i * 2
        """)
        funcdef = self.mod.get_funcdef("foo")
        scope = scopes.by_funcdef(funcdef)
        assert scope._symbols == {
            "_$iter0": MatchSymbol("_$iter0", "var"),
            "i": MatchSymbol("i", "var"),
            "x": MatchSymbol("x", "var"),
            "@return": MatchSymbol("@return", "var"),
            "range": MatchSymbol("range", "const", level=1),
            "i32": MatchSymbol("i32", "const", level=2),
        }

    def test_for_loop_multiple(self):
        scopes = self.analyze("""
        # XXX kill this when 'range' becomes a builtin
        def range(n: i32) -> dynamic:
            pass

        def foo() -> None:
            for i in range(10):
                x: i32 = i * 2
            for j in range(5):
                y: i32 = j * 3
        """)
        funcdef = self.mod.get_funcdef("foo")
        scope = scopes.by_funcdef(funcdef)
        assert scope._symbols == {
            "_$iter0": MatchSymbol("_$iter0", "var"),
            "_$iter1": MatchSymbol("_$iter1", "var"),
            "i": MatchSymbol("i", "var"),
            "j": MatchSymbol("j", "var"),
            "x": MatchSymbol("x", "var"),
            "y": MatchSymbol("y", "var"),
            "@return": MatchSymbol("@return", "var"),
            "range": MatchSymbol("range", "const", level=1),
            "i32": MatchSymbol("i32", "const", level=2),
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
            "x": MatchSymbol("x", "const", hints=("global-const",)),
            "y": MatchSymbol("y", "var", storage="cell", hints=()),
            "i32": MatchSymbol("i32", "const", level=1),
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
            "a": MatchSymbol("a", "const", hints=("blue-param",)),
            "args": MatchSymbol("args", "const", hints=("blue-param",)),
            "@return": MatchSymbol("@return", "var", hints=()),
        }
