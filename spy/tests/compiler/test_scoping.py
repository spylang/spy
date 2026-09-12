from spy.errors import SPyError
from spy.tests.support import (
    CompilerTest,
    expect_errors,
    only_interp,
)


class TestScoping(CompilerTest):
    """
    These tests are loosely based on the snippets in docs/src/reference/scoping.md
    """

    # ======= strict scoping tests =======

    def test_strict_decl_forms(self):
        src = """
        from __spy__ import strict_scoping

        def foo() -> i32:
            var x: i32 = 42
            return x
        """
        mod = self.compile(src)
        assert mod.foo() == 42

    def test_strict_decl_use_before_ok_across_functions(self):
        src = """
        from __spy__ import strict_scoping

        def foo() -> i32:
            return x

        const x: i32 = 42
        """
        mod = self.compile(src)
        assert mod.foo() == 42

    def test_strict_decl_use_before(self):
        src = """
        from __spy__ import strict_scoping

        def foo() -> None:
            x
            var x: i32 = 1
        """
        errors = expect_errors(
            "name `x` is not defined",
            ("used before its declaration", "x"),
            ("declared later here", "var x: i32 = 1"),
        )
        self.compile_raises(src, "foo", errors)

    def test_strict_decl_initializer(self):
        src = """
        from __spy__ import strict_scoping

        def foo() -> i32:
            var x: i32
            x = 42
            return x
        """
        mod = self.compile(src)
        assert mod.foo() == 42

    def test_strict_decl_auto(self):
        src = """
        from __spy__ import strict_scoping

        def foo() -> i32:
            const x: auto = 42
            return x

        def bar() -> str:
            const y = "hello"
            return y
        """
        mod = self.compile(src)
        assert mod.foo() == 42
        assert mod.bar() == "hello"

    def test_strict_decl_auto_no_initializer(self):
        src = """
        from __spy__ import strict_scoping

        def foo() -> i32:
            var x: auto
            x = 42
            return x
        """
        mod = self.compile(src)
        assert mod.foo() == 42

    def test_strict_NameError(self):
        src = """
        from __spy__ import strict_scoping

        def foo() -> None:
            nope
        """
        errors = expect_errors(
            "name `nope` is not defined",
            ("not found in this scope", "nope"),
        )
        self.compile_raises(src, "foo", errors)

    def test_strict_name_resolution(self):
        # [name.resolution]: a name resolves outward, lexically
        src = """
        from __spy__ import strict_scoping

        const K: i32 = 40

        def read_ok() -> i32:
            const x: i32 = 2
            return K + x
        """
        mod = self.compile(src)
        assert mod.read_ok() == 42

    def test_strict_scope_block_if(self):
        src = """
        from __spy__ import strict_scoping

        def foo() -> None:
            if True:
                const x: i32 = 1
            x
        """
        errors = expect_errors(
            "name `x` is not defined",
            ("not found in this scope", "x"),
        )
        self.compile_raises(src, "foo", errors)

    def test_strict_scope_shadow(self):
        src = """
        from __spy__ import strict_scoping

        def foo(cond: bool) -> str:
            const x: str = "outer"
            if cond:
                const x: str = "inner"
                return x
            return x
        """
        mod = self.compile(src)
        assert mod.foo(True) == "inner"
        assert mod.foo(False) == "outer"

    def test_strict_scope_branch_local(self):
        src = """
        from __spy__ import strict_scoping

        def foo() -> None:
            if True:
                var x: i32 = 1
            else:
                var x: i32 = 2
            x
        """
        errors = expect_errors(
            "name `x` is not defined",
            ("not found in this scope", "x"),
        )
        self.compile_raises(src, "foo", errors)

    def test_strict_scope_loop_target(self):
        src = """
        from __spy__ import strict_scoping

        def foo() -> None:
            for i in range(10):
                pass
            i
        """
        errors = expect_errors(
            "name `i` is not defined",
            ("not found in this scope", "i"),
            ("help: declare `var i: auto` before the loop", "i"),
        )
        self.compile_raises(src, "foo", errors)

    def test_strict_scope_loop_target_body(self):
        src = """
        from __spy__ import strict_scoping

        def foo(n: i32) -> i32:
            var total: i32 = 0
            for i in range(n):
                total = total + i
            return total
        """
        mod = self.compile(src)
        assert mod.foo(4) == 6

    def test_strict_scope_loop_target_declare(self):
        src = """
        from __spy__ import strict_scoping

        def foo() -> i32:
            var i: auto
            for i in range(3):
                pass
            return i
        """
        mod = self.compile(src)
        assert mod.foo() == 2

    def test_strict_scope_loop_target_declare_type_mismatch(self):
        src = """
        from __spy__ import strict_scoping

        def foo() -> None:
            var i: str
            for i in range(10):
                pass
        """
        errors = expect_errors(
            "mismatched types",
            ("expected `str`, got `i32`", "i"),
            ("expected `str` because of type declaration", "str"),
        )
        self.compile_raises(src, "foo", errors)

    @only_interp
    def test_strict_scope_loop_fresh(self):
        # [scope.loop-fresh]: a block-local is fresh (unassigned) on each loop
        # iteration; `x` is assigned only when i == 0, so reading it when i == 1
        # is a read from an uninitialized local. Only interp catches this; in
        # compiled mode reading an uninitialized local is UB (see
        # [decl.initializer]).
        src = """
        from __spy__ import strict_scoping

        def foo() -> None:
            for i in range(3):
                var x: i32
                if i == 0:
                    x = 1
                x
        """
        mod = self.compile(src)
        with SPyError.raises("W_Exception", match="read from uninitialized local"):
            mod.foo()

    def test_strict_scope_loop_fresh_reassigned(self):
        # [scope.loop-fresh]: the block-local `x` is redeclared fresh on each
        # iteration and assigned every time, so the loop runs without a
        # re-declaration error.
        src = """
        from __spy__ import strict_scoping

        def foo() -> i32:
            var total: i32 = 0
            for i in range(4):
                var x: i32 = i * 2
                total = total + x
            return total
        """
        mod = self.compile(src)
        assert mod.foo() == 0 + 2 + 4 + 6

    def test_strict_scope_branch_local_shared(self):
        src = """
        from __spy__ import strict_scoping

        def foo(cond: bool) -> i32:
            var x: i32
            if cond:
                x = 1
            else:
                x = 2
            return x
        """
        mod = self.compile(src)
        assert mod.foo(True) == 1
        assert mod.foo(False) == 2

    def test_strict_global_read(self):
        # [global.write]: reading a module-level `var` from a function is fine.
        src = """
        from __spy__ import strict_scoping

        var x: i32 = 42

        def f() -> i32:
            return x
        """
        mod = self.compile(src)
        assert mod.f() == 42

    def test_strict_global_write(self):
        # [global.write]: assigning to a module-level binding without `global`
        # is an error.
        src = """
        from __spy__ import strict_scoping

        var y: i32 = 43

        def f() -> None:
            y = 0
        """
        errors = expect_errors(
            "`y` cannot be re-assigned without a `global` declaration",
            ("`y` is a global", "y"),
            ("help: add `global y` earlier", "y"),
            ("`y` is declared here", "var y: i32 = 43"),
        )
        self.compile_raises(src, "f", errors)

    def test_strict_global_write_declared(self):
        # [global.write]: with an explicit `global x`, a function can mutate the
        # module-level `x`.
        src = """
        from __spy__ import strict_scoping

        var x: i32 = 42

        def get_x() -> i32:
            return x

        def set_x(newval: i32) -> None:
            global x
            x = newval
        """
        mod = self.compile(src)
        assert mod.get_x() == 42
        mod.set_x(100)
        assert mod.get_x() == 100

    # ======= pythonic scoping tests =======

    def test_py_something(self):
        # just a placeholder
        pass
