import textwrap

import pytest

from spy.backend.spy import FQN_FORMAT, SPyBackend
from spy.util import print_diff
from spy.vm.vm import SPyVM


@pytest.mark.usefixtures("init")
class TestDoppler:
    @pytest.fixture
    def init(self, tmpdir):
        # XXX there is a lot of code duplication with CompilerTest
        self.tmpdir = tmpdir
        self.vm = SPyVM()
        self.vm.path.append(str(self.tmpdir))

    def redshift(self, src: str) -> None:
        f = self.tmpdir.join("test.spy")
        src = textwrap.dedent(src)
        f.write(src)
        self.vm.import_("test")
        self.vm.redshift(error_mode="eager")

    def assert_dump(self, expected: str, *, fqn_format: FQN_FORMAT = "short") -> None:
        b = SPyBackend(self.vm, fqn_format=fqn_format)
        got = b.dump_mod("test").strip()
        expected = textwrap.dedent(expected).strip()
        if got != expected:
            print_diff(expected, got, "expected", "got")
            pytest.fail("assert_dump failed")

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
        def foo(x: i32) -> i32:
            return x
        """
        self.redshift(src)
        self.assert_dump(src)

    def test_funcargs(self):
        src = """
        def foo(x: i32, y: i32) -> i32:
            return x + y
        """
        self.redshift(src)
        self.assert_dump(src)

    def test_fqn_format(self):
        src = """
        def foo(x: i32) -> None:
            var y: str = 'hello'
        """
        self.redshift(src)
        expected = """
        def `test::foo`(x: `builtins::i32`) -> `types::NoneType`:
            y: `builtins::str` = 'hello'
        """
        self.assert_dump(expected, fqn_format="full")

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

    def test_blue_local_assign(self):
        self.redshift("""
        def foo() -> i32:
            x = 42
            return x
        """)
        self.assert_dump("""
        def foo() -> i32:
            return 42
        """)

    def test_blue_local_vardef(self):
        self.redshift("""
        def foo() -> i32:
            x: i32 = 42
            return x
        """)
        self.assert_dump("""
        def foo() -> i32:
            return 42
        """)

    def test_assignexpr_argument_is_not_folded(self):
        self.redshift("""
        def inc(x: i32) -> i32:
            return x + 1

        def foo() -> i32:
            x = 0
            y = inc(x := 1)
            return x + y
        """)
        self.assert_dump("""
        def inc(x: i32) -> i32:
            return x + 1

        def foo() -> i32:
            x: i32
            x = 0
            y: i32
            y = `test::inc`(x := 1)
            return x + y
        """)

    def test_assignexpr_const_target_is_folded(self):
        self.redshift("""
        def foo(x: i32) -> None:
            pass

        def main() -> None:
            x = 0
            foo(x := 1)
            foo(y := 2)
            print(x)
            print(y)
        """)
        self.assert_dump("""
        def foo(x: i32) -> None:
            pass

        def main() -> None:
            x: i32
            x = 0
            `test::foo`(x := 1)
            `test::foo`(2)
            print_i32(x)
            print_i32(2)
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
            def fn() -> None:
                print('fn')

            def foo() -> None:
                fn()
                fn()
            return foo

        def main() -> None:
            make_foo()()
        """)
        self.assert_dump("""
        def main() -> None:
            `test::make_foo::foo`()

        def `test::make_foo::fn`() -> None:
            print_str('fn')

        def `test::make_foo::foo`() -> None:
            `test::make_foo::fn`()
            `test::make_foo::fn`()
        """)

    def test_binops(self):
        src = """
        def foo(i: i32, f: f64) -> None:
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
            return [1, 3*4]
        """
        self.redshift(src)
        self.assert_dump("""
        def foo() -> dynamic:
            return \
`_list::list[i32]::_ListImpl::_push`(\
`_list::list[i32]::_ListImpl::_push`(\
`_list::list[i32]::_ListImpl::__new__`(), 1), 12)
        """)

    def test_type_conversion(self):
        src = """
        def foo(x: f64) -> None:
            pass

        def convert_in_call() -> None:
            foo(42)

        def convert_in_locals(x: i32) -> bool:
            flag: bool = x
            return x

        def convert_in_conditions(x: i32) -> None:
            if x:
                pass
        """
        self.redshift(src)
        self.assert_dump("""
        def foo(x: f64) -> None:
            pass

        def convert_in_call() -> None:
            `test::foo`(`operator::i32_to_f64`(42))

        def convert_in_locals(x: i32) -> bool:
            flag: bool = `operator::i32_to_bool`(x)
            return `operator::i32_to_bool`(x)

        def convert_in_conditions(x: i32) -> None:
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

        def foo() -> None:
            x = add(i32)(1, 2)
            y = add(str)("a", "b")
        """)
        self.assert_dump("""
        def foo() -> None:
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
        def foo() -> None:
            x = 1
        """)
        self.assert_dump("""
        def foo() -> None:
            `test::x` = 1
        """)

    def test_format_prebuilt_exception(self):
        fname = str(self.tmpdir.join("test.spy"))
        self.redshift("""
        def foo() -> None:
            raise TypeError('foo')
            raise ValueError
        """)
        # in full mode, we show a call to operator::raise
        expected = f"""
        def `test::foo`() -> `types::NoneType`:
            `operator::raise`('TypeError', 'foo', '{fname}', 3)
            `operator::raise`('ValueError', '', '{fname}', 4)
        """
        self.assert_dump(expected, fqn_format="full")

        # in short mode, we show just a raise
        self.assert_dump("""
        def foo() -> None:
            raise TypeError('foo') # /.../test.spy:3
            raise ValueError # /.../test.spy:4
        """)

    def test_ast_color_map_populated(self, monkeypatch):
        # Verify that when vm.ast_color_map is not None, redshift populates it
        monkeypatch.setattr(self.vm, "ast_color_map", {})
        src = """
        def foo(i: i32) -> i32:
            return i + 2
        """
        self.redshift(src)

        # src contains 4 nodes, 3 red and 1 blue
        assert self.vm
        assert self.vm.ast_color_map
        assert len(self.vm.ast_color_map) == 4
        assert len([c for c in self.vm.ast_color_map.values() if c == "blue"]) == 1
        assert len([c for c in self.vm.ast_color_map.values() if c == "red"]) == 3

    def test_dumper_uses_ast_color_map_for_bg(self, monkeypatch):
        # Verify that Dumper._dump_node passes correct bg argument based on ast_color_map
        from unittest.mock import Mock

        from spy.ast_dump import Dumper

        red_node = Mock()
        blue_node = Mock()

        monkeypatch.setattr(
            self.vm, "ast_color_map", {red_node: "red", blue_node: "blue"}
        )
        dumper = Dumper(use_colors=True, vm=self.vm)
        mock_write = Mock()
        monkeypatch.setattr(dumper, "write", mock_write)

        dumper._dump_node(red_node, "test", [], text_color="turquoise")
        mock_write.assert_any_call("test", color=None, bg="red")

        mock_write.reset_mock()

        dumper._dump_node(blue_node, "test", [], text_color="turquoise")
        mock_write.assert_any_call("test", color=None, bg="blue")
