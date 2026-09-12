import textwrap

import pytest

from spy.analyze.scope2 import ScopeAnalyzer
from spy.parser import Parser
from spy.tests.support import MatchAnnotation, expect_errors
from spy.util import print_diff


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
        self.sa = ScopeAnalyzer("test", self.mod)
        self.sa.analyze()
        return self.sa

    def expect_errors(self, src: str, main: str, *anns: MatchAnnotation):
        with expect_errors(main, *anns):
            self.analyze(src)

    def assert_dump(self, *args: str):
        # the symtable names to dump come first, `expected` is the last arg:
        #   assert_dump(expected)
        #   assert_dump("test::foo", "test::bar", expected)
        *symtable_names, expected = args
        got = self.sa.dump(*symtable_names).strip()
        expected = textwrap.dedent(expected).strip()
        if got != expected:
            print_diff(expected, got, "expected", "got")
            pytest.fail("assert_dump failed")

    def test_dump(self):
        src = """
        from __spy__ import strict_scoping

        const K: i32 = 42

        def foo() -> i32:
            const x: i32 = 1
            const y: i32 = 1
            if K:
                const y = 10
                const z = x + y
        """
        self.analyze(src)
        expected = """
        symtable test (module):
            strict_scoping: Symbol("strict_scoping", "const", "auto") => <ImportRef __spy__.strict_scoping>
            K: Symbol("K", "const", "explicit")
            foo: Symbol("foo", "const", "funcdef")

            scope test:
                K -> K
                i32 -> i32 @ builtins (depth=1) => <ImportRef builtins.i32>

        symtable test::foo (function):
            @return: Symbol("@return", "var", "auto")
            x$0: Symbol("x", "const", "explicit")
            y$0: Symbol("y", "const", "explicit")
            y$1: Symbol("y", "const", "explicit")
            z$0: Symbol("z", "const", "explicit")

            scope foo:
                x -> x$0
                i32 -> i32 @ builtins (depth=2) => <ImportRef builtins.i32>
                y -> y$0
                K -> K @ test (depth=1)
                scope if.then:
                    y -> y$1
                    z -> z$0
                    x -> x$0
        """
        self.assert_dump(expected)

    def test_decl_forms(self):
        # [decl.forms]: var and const declarations inside a function
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
        self.analyze(src)
        expected = """
        symtable test::foo (function):
            @return: Symbol("@return", "var", "auto")
            a$0: Symbol("a", "var", "explicit")
            b$0: Symbol("b", "const", "explicit")
            c$0: Symbol("c", "var", "explicit")
            d$0: Symbol("d", "const", "explicit")
            e$0: Symbol("e", "var", "explicit")
            f$0: Symbol("f", "var", "explicit")
            g$0: Symbol("g", "var", "explicit")

            scope foo:
                a -> a$0
                i32 -> i32 @ builtins (depth=2) => <ImportRef builtins.i32>
                b -> b$0
                c -> c$0
                d -> d$0
                e -> e$0
                f -> f$0
                g -> g$0
        """
        self.assert_dump("test::foo", expected)

    def test_decl_use_before(self):
        # [decl.use-before]: the use resolves lazily to a NameError (used before
        # its declaration)
        src = """
        from __spy__ import strict_scoping

        def foo() -> None:
            x
            var x: i32 = 1
        """
        self.analyze(src)
        expected = """
        symtable test::foo (function):
            @return: Symbol("@return", "var", "auto")
            x$0: Symbol("x", "var", "explicit")

            scope foo:
                x -> NameError
                i32 -> i32 @ builtins (depth=2) => <ImportRef builtins.i32>
        """
        self.assert_dump("test::foo", expected)

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
        self.analyze(src)
        expected = """
        symtable test::foo (function):
            @return: Symbol("@return", "var", "auto")

            scope foo:
                nope -> NameError
        """
        self.assert_dump("test::foo", expected)

    def test_scope_block_if(self):
        # [scope.block]: a name declared inside an if body is not visible
        # outside. The block-local `x` lives in the function symtable (x$0), is
        # visible as `x -> x$0` inside if.then, but resolves to NameError in the
        # enclosing `foo` scope. Names used inside the block still capture from
        # outer frames (K -> K @ test), showing captures propagate through blocks.
        src = """
        from __spy__ import strict_scoping

        const K: i32 = 42

        def foo(cond: bool) -> None:
            if cond:
                const x: i32 = K
            x
        """
        self.analyze(src)
        expected = """
        symtable test::foo (function):
            cond$0: Symbol("cond", "var", "red-param")
            @return: Symbol("@return", "var", "auto")
            x$0: Symbol("x", "const", "explicit")

            scope foo:
                cond -> cond$0
                x -> NameError
                scope if.then:
                    x -> x$0
                    i32 -> i32 @ builtins (depth=2) => <ImportRef builtins.i32>
                    K -> K @ test (depth=1)
        """
        self.assert_dump("test::foo", expected)

    def test_scope_loop_target(self):
        # [scope.loop-target]: the for target `i` (and the hidden iterator) are
        # block-local to the loop body; `i` resolves to NameError after the loop.
        src = """
        from __spy__ import strict_scoping

        def foo() -> None:
            for i in range(10):
                pass
            i
        """
        self.analyze(src)
        expected = """
        symtable test::foo (function):
            @return: Symbol("@return", "var", "auto")
            _$iter$0: Symbol("_$iter", "var", "auto")
            i$0: Symbol("i", "var", "loop-target")

            scope foo:
                range -> range @ builtins (depth=2) => <ImportRef _range.range>
                _$iter -> _$iter$0
                i -> NameError
                scope for.body:
                    i -> i$0
        """
        self.assert_dump("test::foo", expected)

    def test_scope_loop_target_declare(self):
        # [scope.loop-target-declare]: if a binding of the same name already
        # exists in an enclosing block, the loop target reuses it (i$0) instead
        # of creating a fresh block-local. So `i` is visible after the loop.
        src = """
        from __spy__ import strict_scoping

        def foo() -> None:
            var i: auto
            for i in range(3):
                pass
            i
        """
        self.analyze(src)
        expected = """
        symtable test::foo (function):
            @return: Symbol("@return", "var", "auto")
            i$0: Symbol("i", "var", "explicit")
            _$iter$0: Symbol("_$iter", "var", "auto")

            scope foo:
                i -> i$0
                range -> range @ builtins (depth=2) => <ImportRef _range.range>
                _$iter -> _$iter$0
                scope for.body:
                    i -> i$0
        """
        self.assert_dump("test::foo", expected)

    def test_name_class_skip(self):
        # [name.class-skip]: class scopes are skipped by method bodies. A bare
        # reference to a field name inside a method resolves to NameError (the
        # user must write `self.x`).
        src = """
        from __spy__ import strict_scoping

        @struct
        class P:
            x: i32
            def get(self: P) -> i32:
                return x
        """
        self.analyze(src)
        expected = """
        symtable test::P::get (function):
            self$0: Symbol("self", "var", "red-param")
            @return: Symbol("@return", "var", "auto")

            scope get:
                self -> self$0
                x -> NameError
        """
        self.assert_dump("test::P::get", expected)

    def test_global_write(self):
        # [global.write]: a function can READ a module-level name freely, but
        # ASSIGNING to it without a `global` declaration is an error.
        src = """
        from __spy__ import strict_scoping

        var x: i32 = 42
        var y: i32 = 43

        def f() -> None:
            print(x)
            y = 0
        """
        self.analyze(src)
        expected = """
        symtable test::f (function):
            @return: Symbol("@return", "var", "auto")

            scope f:
                print -> print @ builtins (depth=2) => <ImportRef builtins.print>
                x -> x @ test (depth=1)
                y -> ScopeError
        """
        self.assert_dump("test::f", expected)

    def test_global_write_declared(self):
        # [global.write]: with an explicit `global y`, assigning to the
        # module-level `y` is allowed; the target resolves to the global. The
        # `global y` declaration is shown in the scope dump.
        src = """
        from __spy__ import strict_scoping

        var y: i32 = 43

        def f() -> None:
            global y
            y = 0
        """
        self.analyze(src)
        expected = """
        symtable test (module):
            strict_scoping: Symbol("strict_scoping", "const", "auto") => <ImportRef __spy__.strict_scoping>
            y: Symbol("y", "var", "explicit") [cell]
            f: Symbol("f", "const", "funcdef")

            scope test:
                y -> y
                i32 -> i32 @ builtins (depth=1) => <ImportRef builtins.i32>

        symtable test::f (function):
            @return: Symbol("@return", "var", "auto")

            scope f:
                global y
                y -> y @ test (depth=1)
        """
        self.assert_dump(expected)

    def test_global_read_is_noop(self):
        # a `global y` followed by a READ resolves outward to the module `y`,
        # exactly as if the `global` were not there.
        src = """
        from __spy__ import strict_scoping

        var y: i32 = 43

        def f() -> i32:
            global y
            return y
        """
        self.analyze(src)
        expected = """
        symtable test::f (function):
            @return: Symbol("@return", "var", "auto")

            scope f:
                global y
                y -> y @ test (depth=1)
        """
        self.assert_dump("test::f", expected)

    def test_global_is_per_scope(self):
        # `global` is a per-scope property: a `global y` in the `else` branch
        # does not conflict with a branch-local `var y` in the `then` branch.
        # In `then`, `y` is the block-local y$0; in `else`, the write resolves
        # to the module `y`.
        src = """
        from __spy__ import strict_scoping

        var y: i32 = 0

        def foo(cond: bool) -> None:
            if cond:
                var y: i32 = 1
            else:
                global y
                y = 2
        """
        self.analyze(src)
        expected = """
        symtable test::foo (function):
            cond$0: Symbol("cond", "var", "red-param")
            @return: Symbol("@return", "var", "auto")
            y$0: Symbol("y", "var", "explicit")

            scope foo:
                cond -> cond$0
                scope if.then:
                    y -> y$0
                    i32 -> i32 @ builtins (depth=2) => <ImportRef builtins.i32>
                scope if.else:
                    global y
                    y -> y @ test (depth=1)
        """
        self.assert_dump("test::foo", expected)

    def test_global_define_conflict(self):
        # rule 1: declaring `global y` and then defining a local `y` in the SAME
        # scope is an error.
        src = """
        from __spy__ import strict_scoping

        var y: i32 = 0

        def foo() -> None:
            global y
            var y: i32 = 1
        """
        self.expect_errors(
            src,
            "variable `y` is already declared as global",
            ("this is the new declaration", "var y: i32 = 1"),
            ("`y` was declared global here", "global y"),
        )

    def test_scope_shadow(self):
        # [scope.shadow]: an inner block may shadow an outer name. Inside if.then
        # `x` resolves to the block-local x$1; outside it resolves to x$0.
        src = """
        from __spy__ import strict_scoping

        def foo(cond: bool) -> str:
            const x: str = "outer"
            if cond:
                const x: str = "inner"
                return x
            return x
        """
        self.analyze(src)
        expected = """
        symtable test::foo (function):
            cond$0: Symbol("cond", "var", "red-param")
            @return: Symbol("@return", "var", "auto")
            x$0: Symbol("x", "const", "explicit")
            x$1: Symbol("x", "const", "explicit")

            scope foo:
                cond -> cond$0
                x -> x$0
                str -> str @ builtins (depth=2) => <ImportRef builtins.str>
                scope if.then:
                    x -> x$1
                    str -> str @ builtins (depth=2) => <ImportRef builtins.str>
        """
        self.assert_dump("test::foo", expected)
