import textwrap
import pytest
from spy import ast
from spy.vm.vm import SPyVM
from spy.vm.function import W_ASTFunc
from spy.backend.spy import SPyBackend, FQN_FORMAT
from spy.util import print_diff

@pytest.mark.usefixtures('init')
class TestDoppler:

    @pytest.fixture
    def init(self, tmpdir):
        # XXX there is a lot of code duplication with CompilerTest
        self.tmpdir = tmpdir
        self.vm = SPyVM()
        self.vm.path.append(str(self.tmpdir))

    def redshift(self, src: str) -> None:
        f = self.tmpdir.join('test.spy')
        src = textwrap.dedent(src)
        f.write(src)
        w_mod = self.vm.import_('test')
        self.vm.redshift()

    def assert_dump(self, expected: str,
                    *, fqn_format: FQN_FORMAT='short') -> None:
        b = SPyBackend(self.vm, fqn_format = fqn_format)
        got = b.dump_mod('test').strip()
        expected = textwrap.dedent(expected).strip()
        if got != expected:
            print_diff(expected, got, 'expected', 'got')
            pytest.fail('assert_dump failed')

    def test_simple(self):
        src = """
        def foo() -> i32:
            return 1 + 2
        """
        self.redshift(src)
        self.assert_dump("""
        def foo() -> i32:
            return 3
        """)

    def test_red_vars(self):
        src = """
        def foo() -> i32:
            x: i32 = 1
            return x
        """
        self.redshift(src)
        expected = """
        def foo() -> i32:
            x: i32
            x = 1
            return x
        """
        self.assert_dump(expected)

    def test_funcargs(self):
        src = """
        def foo(x: i32, y: i32) -> i32:
            return x + y
        """
        self.redshift(src)
        self.assert_dump(src)

    def test_fqn_format(self):
        src = """
        def foo(x: i32) -> void:
            y: str = 'hello'
        """
        self.redshift(src)
        expected = """
        def foo(x: `builtins::i32`) -> `builtins::void`:
            y: `builtins::str`
            y = 'hello'
        """
        self.assert_dump(expected, fqn_format='full')

    def test_op_between_red_and_blue(self):
        src = """
        def foo(x: i32) -> i32:
            return x + 1
        """
        self.redshift(src)
        self.assert_dump(src)

    def test_dont_redshift_function_calls(self):
        src = """
        def inc(x: i32) -> i32:
            return x + 1

        def foo() -> i32:
            return inc(5)
        """
        self.redshift(src)
        expected = """
        def inc(x: i32) -> i32:
            return x + 1

        def foo() -> i32:
            return `test::inc`(5)
        """
        self.redshift(src)
        self.assert_dump(expected)

    def test_blue_call(self):
        self.redshift("""
        @blue
        def ANSWER() -> i32:
            return 42

        def foo() -> i32:
            return ANSWER()
        """)
        self.assert_dump("""
        def foo() -> i32:
            return 42
        """)

    def test_call_blue_closure(self):
        self.redshift("""
        @blue
        def make_fn():
            def fn(x: i32) -> i32:
                return x * 2
            return fn

        def foo() -> i32:
            return make_fn()(21)
        """)
        self.assert_dump("""
        def foo() -> i32:
            return `test::fn#0`(21)

        def `test::fn#0`(x: i32) -> i32:
            return x * 2
        """)

    def test_binops(self):
        src = """
        def foo(i: i32, f: f64) -> void:
            i + i
            i - i
            i * i
            i / i
            i == i
            i != i
            i < i
            i <= i
            i > i
            i >= i
            f + f
            f - f
            f * f
            f / f
            f == f
            f != f
            f < f
            f <= f
            f > f
            f >= f
        """
        self.redshift(src)
        self.assert_dump(src)
