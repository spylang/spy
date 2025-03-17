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
        def `test::foo`(x: `builtins::i32`) -> `builtins::void`:
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
            return `test::make_fn::fn`(21)

        def `test::make_fn::fn`(x: i32) -> i32:
            return x * 2
        """)

    def test_call_func_already_redshifted(self):
        self.redshift("""
        @blue
        def make_foo():
            def fn() -> void:
                print('fn')

            def foo() -> void:
                fn()
                fn()
            return foo

        def main() -> void:
            make_foo()()
        """)
        self.assert_dump("""
        def main() -> void:
            `test::make_foo::foo`()

        def `test::make_foo::fn`() -> void:
            print_str('fn')

        def `test::make_foo::foo`() -> void:
            `test::make_foo::fn`()
            `test::make_foo::fn`()
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

    def test_list(self):
        src = """
        def foo() -> dynamic:
            return [1, 2, 3+4]
        """
        self.redshift(src)
        self.assert_dump("""
        def foo() -> dynamic:
            return [1, 2, 7]
        """)

    def test_type_conversion(self):
        src = """
        def foo(x: f64) -> void:
            pass

        def convert_in_call() -> void:
            foo(42)

        def convert_in_locals(x: i32) -> bool:
            flag: bool = x
            return x

        def convert_in_conditions(x: i32) -> void:
            if x:
                pass
        """
        self.redshift(src)
        self.assert_dump("""
        def foo(x: f64) -> void:
            pass

        def convert_in_call() -> void:
            `test::foo`(`operator::i32_to_f64`(42))

        def convert_in_locals(x: i32) -> bool:
            flag: bool
            flag = `operator::i32_to_bool`(x)
            return `operator::i32_to_bool`(x)

        def convert_in_conditions(x: i32) -> void:
            if `operator::i32_to_bool`(x):
                pass
        """)

    def test_blue_namespace(self):
        self.redshift("""
        @blue
        def add(T):
            def impl(x: T, y: T) -> T:
                return x + y
            return impl

        def foo() -> void:
            x = add(i32)(1, 2)
            y = add(str)("a", "b")
        """)
        self.assert_dump("""
        def foo() -> void:
            x: i32
            x = `test::add[i32]::impl`(1, 2)
            y: str
            y = `test::add[str]::impl`('a', 'b')

        def `test::add[i32]::impl`(x: i32, y: i32) -> i32:
            return x + y

        def `test::add[str]::impl`(x: str, y: str) -> str:
            return `operator::str_add`(x, y)
        """)

    def test_store_outer_var(self):
        self.redshift("""
        var x: i32 = 0
        def foo() -> void:
            x = 1
        """)
        self.assert_dump("""
        def foo() -> void:
            x = 1
        """)

    def test_format_prebuilt_exception(self):
        self.redshift("""
        def foo(x: bool) -> void:
            if x:
                raise Exception('foo')
            else:
                raise Exception('bar')
        """)
        self.assert_dump("""
        def foo(x: bool) -> void:
            if x:
                raise Exception('foo')
            else:
                raise Exception('bar')
        """)
