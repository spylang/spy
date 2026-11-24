import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest, expect_errors, only_interp, skip_backends


class TestMisc(CompilerTest):
    def test_COLOR(self):
        mod = self.compile("""
        from __spy__ import COLOR

        def foo() -> str:
            x = 42
            return COLOR(x)

        def bar() -> str:
            x = 42
            x = 43
            return COLOR(x)
        """)
        assert mod.foo() == "blue"
        assert mod.bar() == "red"

    def test_is_compiled(self):
        mod = self.compile("""
        from __spy__ import is_compiled

        def foo() -> bool:
            return is_compiled()
        """)
        if self.backend in ("interp", "doppler"):
            assert mod.foo() == False
        else:
            assert mod.foo() == True

    def test_as_red(self):
        src = """
        from __spy__ import COLOR, as_red

        def foo() -> str:
            return COLOR(as_red(42))
        """
        mod = self.compile(src)
        assert mod.foo() == "red"

    @only_interp
    def test_lookup_fqn(self):
        src = """
        from __spy__ import lookup_fqn

        def foo() -> str:
            bar = lookup_fqn('test::bar')
            return bar() + '-foo'
        """
        self.write_file("y.spy", src)
        #
        mod = self.compile("""
        from y import foo

        def bar() -> str:
            return 'bar'

        def main() -> str:
            return foo() + '-main'
        """)
        assert mod.main() == "bar-foo-main"

    @only_interp
    def test_lookup_fqn_not_found(self):
        src = """
        from __spy__ import lookup_fqn

        w_x = lookup_fqn("test::does_not_exist")
        """
        with SPyError.raises("W_ValueError", match="FQN not found"):
            self.compile(src)

    @only_interp
    def test_unchecked_pure_decorator(self):
        mod = self.compile("""
        from __spy__ import unchecked_pure_trust_me, COLOR

        @unchecked_pure_trust_me
        def inc(x: i32) -> i32:
            return x + 1

        def foo() -> str:
            return COLOR(inc(10))

        def bar(x: i32) -> str:
            return COLOR(inc(x))

        """)
        assert mod.inc.w_func.is_pure()
        assert mod.foo() == "blue"
        assert mod.bar(1) == "red"

    def test_cannot_apply_unchecked_pure_to_blue_func(self):
        src = """
        from __spy__ import unchecked_pure_trust_me

        @unchecked_pure_trust_me
        @blue
        def foo():
            return 42

        def main() -> None:
            pass
        """
        errors = expect_errors(
            "@unchecked_pure_trust_me cannot be applied to @blue functions",
            ("this is not a red function", "def foo():"),
        )
        self.compile_raises(src, "main", errors, error_reporting="eager")

    def test_unchecked_pure_trust_me_blue_call_raises_static_error(self):
        src = """
        from __spy__ import unchecked_pure_trust_me

        @unchecked_pure_trust_me
        def ensure_positive(x: i32) -> i32:
            if x < 0:
                raise ValueError("x is negative")
            return x

        def foo() -> i32:
            return ensure_positive(-1)
        """
        errors = expect_errors(
            "x is negative",
        )
        # On interp, the error happens at runtime. On doppler/C, it is caught at
        # redshift time and reported as StaticError
        if self.backend == "interp":
            self.compile_raises(src, "foo", errors)
        else:
            self.compile_raises(src, "foo", errors, error_reporting="eager")

    def test_specialize(self):
        src = """
        from __spy__ import Specialized, specialize

        @blue
        def call_specialize():
            return specialize(3)

        def getval() -> i32:
            s = call_specialize()
            return s.val

        def getrepr_instance() -> str:
            s = call_specialize()
            return repr(s)

        def getrepr_type() -> str:
            s = call_specialize()
            return repr(type(s))

        def Specialized_ctor_is_same_as_specialize() -> bool:
            T = Specialized[3]
            return call_specialize() == T()
        """
        mod = self.compile(src)
        assert mod.getval() == 3
        assert mod.getrepr_instance() == "specialize(3)"
        assert mod.getrepr_type() == "<spy type '_specialize::Specialized[3]'>"
        assert mod.Specialized_ctor_is_same_as_specialize()
