import textwrap
from typing import Optional

import pytest

from spy import ast
from spy.analyze.symtable import Color
from spy.backend.spy import FQN_FORMAT, SPyBackend
from spy.errors import SPyError
from spy.fqn import FQN
from spy.util import print_diff
from spy.vm.function import W_ASTFunc
from spy.vm.vm import SPyVM


@pytest.mark.usefixtures("init")
class TestDoppler:
    @pytest.fixture
    def init(self, tmpdir):
        # XXX there is a lot of code duplication with CompilerTest
        self.tmpdir = tmpdir
        self.vm = SPyVM()
        self.vm.path.append(str(self.tmpdir))

    def import_src(self, src: str) -> None:
        f = self.tmpdir.join("test.spy")
        src = textwrap.dedent(src)
        f.write(src)
        self.vm.import_("test")

    def redshift(self, src: str, *, error_mode="eager") -> None:
        self.import_src(src)
        self.vm.redshift(error_mode=error_mode)

    def assert_dump(
        self,
        expected: str,
        *,
        fqn_format: FQN_FORMAT = "short",
        funcname: Optional[str] = None,
    ) -> None:
        b = SPyBackend(self.vm, fqn_format=fqn_format)
        if funcname is not None:
            fqn = FQN(f"test::{funcname}")
            w_func = self.vm.globals_w[fqn]
            assert isinstance(w_func, W_ASTFunc)
            b.modname = "test"
            b.dump_w_func(fqn, w_func)
            got = b.out.build().strip()
        else:
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
            x: i32 = 0
            y: i32 = `test::inc`(x := 1)
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
            x: i32 = 0
            `test::foo`(x := 1)
            `test::foo`(2)
            `_print::println[i32]`(x)
            `_print::println[str]`('2')
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
            `_print::println[str]`('fn')

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
`list[i32]::_push`(\
`list[i32]::_push`(\
`list[i32]::new`(), 1), 12)
        """)

    def test_pure_blue_call_folded(self):
        src = """
        def foo() -> f64:
            return 1 + 2.5
        """
        self.redshift(src)
        self.assert_dump("""
        def foo() -> f64:
            return 3.5
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
            x: i32 = `test::add[i32]::impl`(1, 2)
            y: str = `test::add[str]::impl`('a', 'b')

        def `test::add[i32]::impl`(x: i32, y: i32) -> i32:
            return x + y

        def `test::add[str]::impl`(x: str, y: str) -> str:
            return `_str::methods::__add__`(x, y)
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

    def test_ast_color_map_populated(self):
        self.vm.ast_color_map = {}
        src = """
        def foo(i: i32) -> i32:
            return i + 2 * 3
        """
        self.import_src(src)
        w_foo_orig = self.vm.lookup_global(FQN("test::foo"))
        self.redshift(src)
        w_foo_rs = self.vm.lookup_global(FQN("test::foo"))

        def get_color(root: ast.Node, NodeType: type, src: Optional[str]) -> Color:
            assert self.vm.ast_color_map is not None
            node = root.find(NodeType, src)
            return self.vm.ast_color_map[node]

        foo_orig = w_foo_orig.funcdef  # type: ignore
        foo_rs = w_foo_rs.funcdef  # type: ignore

        # check the colors of the original function
        assert get_color(foo_orig, ast.Literal, "2") == "blue"
        assert get_color(foo_orig, ast.BinOp, "2 * 3") == "blue"
        assert get_color(foo_orig, ast.Name, "i") == "red"
        assert get_color(foo_orig, ast.BinOp, "i + 2 * 3") == "red"

        # check the colors of the redshifted function
        #
        # this is the node "6". Keep in mind that get_src() always points to the
        # original src "2 * 3"
        assert get_color(foo_rs, ast.Const, None) == "blue"
        #
        # this is the "+", but it has been shifted into a call to i32_add
        assert get_color(foo_rs, ast.Call, "i + 2 * 3") == "red"

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

    def test_force_inline_not_dumped(self):
        self.redshift("""
        from __spy__ import force_inline

        @force_inline
        def inc(x: i32) -> i32:
            return x + 1

        def foo() -> i32:
            return inc(10)
        """)
        expected = """
        def foo() -> i32:
            return __block__(x$0: i32 = 10; x$0 + 1)
        """
        self.assert_dump(expected)

    def test_force_inline_replaces_call(self):
        self.redshift("""
        from __spy__ import force_inline

        @force_inline
        def inc(x: i32) -> i32:
            return x + 1

        def foo() -> i32:
            return inc(10)
        """)
        expected = """
        def foo() -> i32:
            return __block__(x$0: i32 = 10; x$0 + 1)
        """
        self.assert_dump(expected, funcname="foo")

    def test_force_inline_multiple_sites_unique_names(self):
        self.redshift("""
        from __spy__ import force_inline

        @force_inline
        def inc(x: i32) -> i32:
            return x + 1

        def foo(a: i32, b: i32) -> i32:
            return inc(a) + inc(b)
        """)
        expected = """
        def foo(a: i32, b: i32) -> i32:
            return __block__(x$0: i32 = a; x$0 + 1) + __block__(x$1: i32 = b; x$1 + 1)
        """
        self.assert_dump(expected, funcname="foo")

    def test_force_inline_in_metafunc(self):
        # see also test_force_inline.py:test_metafunc
        self.redshift("""
        from __spy__ import force_inline
        from operator import OpSpec

        @blue.metafunc
        def double(m_x):
            @force_inline
            def impl(x: i32) -> i32:
                return x + x
            return OpSpec(impl)

        def foo() -> i32:
            return double(21)
        """)
        expected = """
        def foo() -> i32:
            return __block__(x$0: i32 = 21; x$0 + x$0)
        """
        self.assert_dump(expected, funcname="foo")

    def test_nested_force_inline(self):
        self.redshift("""
        from __spy__ import force_inline

        @force_inline
        def inc(x: i32) -> i32:
            return x + 1

        @force_inline
        def add2(x: i32) -> i32:
            return inc(inc(x))

        def foo() -> i32:
            return add2(10)
        """)
        expected = """
        def foo() -> i32:
            return __block__(x$0: i32 = 10; __block__(x$1$0: i32 = __block__(x$0$0: i32 = x$0; x$0$0 + 1); x$1$0 + 1))
        """
        self.assert_dump(expected, funcname="foo")

    def test_pure_builtin_method(self):
        self.redshift("""
        def foo() -> str:
            return str(True)
        """)
        self.assert_dump(
            """
        def foo() -> str:
            return 'True'
        """,
            funcname="foo",
        )

    def test_residual_type_conversion(self):
        src = """
        def bar(x: f64) -> None:
            pass

        def foo(x: i32) -> f64:
            bar(x)           # func arg conv
            flag: bool = x   # local var conv
            if x:            # 'if conditional' conv
                pass
            return x         # return value conv
        """
        self.redshift(src)
        self.assert_dump("""
        def bar(x: f64) -> None:
            pass

        def foo(x: i32) -> f64:
            `test::bar`(`operator::i32_to_f64`(x))
            flag: bool = `operator::i32_to_bool`(x)
            if `operator::i32_to_bool`(x):
                pass
            return `operator::i32_to_f64`(x)
       """)

    def test_eager_type_conversion(self):
        src = """
        def bar(x: f64) -> None:
            pass

        def foo() -> f64:
            x = 42
            bar(x)               # func arg conv
            var flag: bool = x   # local var conv
            if x:                # 'if conditional' conv
                pass
            return x             # return value conv
        """
        self.redshift(src)
        self.assert_dump("""
        def bar(x: f64) -> None:
            pass

        def foo() -> f64:
            `test::bar`(42.0)
            flag: bool = True
            if True:
                pass
            return 42.0
        """)

    def test_eager_conversion_becomes_static_error(self):
        src = """
        def foo() -> str:
            x: object = 1
            return x
        """
        with SPyError.raises(
            "W_TypeError", match="Invalid cast. Expected `str`, got `i32`"
        ):
            self.redshift(src)

    def test_eager_conversion_become_lazy_error(self):
        src = """
        def foo() -> str:
            x: object = 1
            return x
        """
        self.redshift(src, error_mode="lazy")
        self.assert_dump("""
        def foo() -> str:
            raise TypeError('Invalid cast. Expected `str`, got `i32`') # /.../test.spy:4
        """)
