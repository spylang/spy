import pytest

from spy.errors import SPyError
from spy.tests.support import (
    CompilerTest,
    expect_errors,
    no_C,
    only_interp,
    skip_backends,
)
from spy.vm.exc import FrameInfo


class MatchFrame:
    def __init__(self, fqn: str, src: str, *, kind: str = "astframe") -> None:
        self.kind = kind
        self.fqn = fqn
        self.src = src

    def __eq__(self, info: object) -> bool:
        if not isinstance(info, FrameInfo):
            return NotImplemented
        return (
            self.kind == info.kind
            and self.fqn == str(info.fqn)
            and self.src == info.loc.get_src()
        )

    def __repr__(self) -> str:
        return f"<MatchFrame({self.fqn!r}, {self.src!r}, kind={self.kind!r})"


class TestException(CompilerTest):
    def test_raise(self):
        # for now, we don't support "except:", and raising an exception result
        # in a panic.
        mod = self.compile("""
        def foo(x: i32) -> i32:
            if x == 0:
                return 42
            elif x == 1:
                raise Exception("hello")   # <-- line 6
            elif x == 2:
                raise ValueError("world")
            elif x == 3:
                raise ValueError()
            else:
                raise IndexError
        """)
        assert mod.foo(0) == 42
        with SPyError.raises("W_Exception", match="hello") as excinfo:
            mod.foo(1)
        with SPyError.raises("W_ValueError", match="world"):
            mod.foo(2)
        with SPyError.raises("W_ValueError") as excinfo:
            mod.foo(3)
            assert excinfo.value.w_exc.message == ""
        with SPyError.raises("W_IndexError") as excinfo:
            mod.foo(4)
            assert excinfo.value.w_exc.message == ""

    def test_cannot_raise_red(self):
        src = """
        def foo() -> None:
            var exc = Exception("hello")
            raise exc
        """
        errors = expect_errors(
            "`raise` only accepts blue values for now",
            ("this is red", "exc"),
        )
        self.compile_raises(src, "foo", errors)

    @skip_backends("C", reason="tracebacks not supported by the C backend")
    def test_traceback(self):
        src = """
        def foo() -> i32:
            return bar(1)

        def bar(x: i32) -> i32:
            return baz(x, 2)

        def baz(x: i32, y: i32) -> i32:
            raise ValueError("hello")
        """
        mod = self.compile(src)
        with SPyError.raises("W_ValueError", match="hello") as exc:
            mod.foo()
        w_tb = exc.value.add_traceback()
        assert w_tb.entries == [
            MatchFrame("test::foo", "bar(1)"),
            MatchFrame("test::bar", "baz(x, 2)"),
            MatchFrame("test::baz", 'raise ValueError("hello")'),
        ]
        exc.value.w_exc.format()  # check that it doesn't fail

    @only_interp
    def test_modframe_classframe_traceback(self):
        src = """
        @blue
        def get_T():
            raise StaticError("invalid type")

        @struct
        class Point:
            x: get_T()
            y: get_T()
        """
        with SPyError.raises("W_StaticError", match="invalid type") as exc:
            mod = self.compile(src)
        w_tb = exc.value.add_traceback()
        assert w_tb.entries == [
            MatchFrame("test", "class Point:", kind="modframe"),
            MatchFrame("test::Point", "get_T()", kind="classframe"),
            MatchFrame("test::get_T", 'raise StaticError("invalid type")'),
        ]
        exc.value.w_exc.format()  # check that it doesn't fail

    def test_doppler_traceback(self):
        src = """
        @blue
        def get_k():
            raise StaticError("hello")

        def bar() -> i32:
            return get_k()

        def foo() -> i32:
            return bar()
        """
        if self.backend == "interp":
            # In [interp] we get an error ONLY when we execute foo, and the taceback is
            # foo->bar->get_k
            mod = self.compile(src)
            with SPyError.raises("W_StaticError", match="hello") as exc:
                mod.foo()

            w_tb = exc.value.add_traceback()
            assert w_tb.entries == [
                MatchFrame("test::foo", "bar()"),
                MatchFrame("test::bar", "get_k()"),
                MatchFrame("test::get_k", 'raise StaticError("hello")'),
            ]

        else:
            # In [doppler] and [C], we get an error during compilation, and traceback is
            # "redshift bar"->get_k.
            with SPyError.raises("W_StaticError", match="hello") as exc:
                self.compile(src)

            w_tb = exc.value.add_traceback()
            assert w_tb.entries == [
                MatchFrame("test::bar", "get_k()", kind="dopplerframe"),
                MatchFrame("test::get_k", 'raise StaticError("hello")'),
            ]

    def test_lazy_error(self):
        src = """
        def foo() -> None:
            1 + "hello"
        """
        mod = self.compile(src, error_mode="lazy")
        with SPyError.raises("W_TypeError", match=r"cannot do `i32` \+ `str`"):
            mod.foo()

    @pytest.mark.parametrize("error_mode", ["lazy", "eager"])
    def test_non_static_errors_are_always_lazy(self, error_mode):
        src = """
        def dead_branch_division() -> None:
            if False:
                1 / 0

        def divide_if_flag(flag: bool) -> None:
            if flag:
                1 / 0

        def short_circuit_and_false() -> bool:
            return False and (1 / 0)

        def short_circuit_or_true() -> bool:
            return True or (1 / 0)

        def short_circuit_and_flag(flag: bool) -> bool:
            return flag and (1 / 0)

        def assert_with_division_message(flag: bool) -> bool:
            assert flag, 1 / 0
            return True
        """
        mod = self.compile(src, error_mode=error_mode)

        mod.dead_branch_division()
        mod.divide_if_flag(False)
        with SPyError.raises("W_ZeroDivisionError", match="division by zero"):
            mod.divide_if_flag(True)

        assert mod.short_circuit_and_false() is False
        assert mod.short_circuit_or_true() is True
        assert mod.short_circuit_and_flag(False) is False
        with SPyError.raises("W_ZeroDivisionError", match="division by zero"):
            mod.short_circuit_and_flag(True)

        assert mod.assert_with_division_message(True) is True
        with SPyError.raises("W_ZeroDivisionError", match="division by zero"):
            mod.assert_with_division_message(False)

    @pytest.mark.parametrize("error_mode", ["lazy", "eager"])
    def test_non_static_errors_preserve_side_effect_order(self, error_mode):
        src = """
        var counter: i32 = 0

        def inc() -> i32:
            counter = counter + 1
            return 10

        def sum_then_divide() -> f64:
            return inc() + (1 / 0)

        def read_counter() -> i32:
            return counter
        """
        mod = self.compile(src, error_mode=error_mode)
        assert mod.read_counter() == 0
        with SPyError.raises("W_ZeroDivisionError", match="division by zero"):
            mod.sum_then_divide()
        assert mod.read_counter() == 1

    @pytest.mark.parametrize("error_mode", ["lazy", "eager"])
    def test_non_static_errors_remain_lazy_in_typed_contexts(self, error_mode):
        src = """
        def must_return_str() -> str:
            return 1 / 0
        """
        mod = self.compile(src, error_mode=error_mode)
        with SPyError.raises("W_ZeroDivisionError", match="division by zero"):
            mod.must_return_str()

    def test_static_errors_are_eager_in_dead_code_and_boolops(self):
        src = """
        def dead_branch_type_error() -> None:
            if False:
                1 + "hello"

        def short_circuit_and_type_error() -> bool:
            return False and (1 + "x")

        def short_circuit_or_type_error() -> bool:
            return True or (1 + "x")
        """
        typeerr = r"cannot do `i32` \+ `str`"
        if self.backend == "interp":
            mod = self.compile(src, error_mode="eager")
            mod.dead_branch_type_error()
            assert mod.short_circuit_and_type_error() is False
            assert mod.short_circuit_or_type_error() is True
        else:
            with SPyError.raises("W_TypeError", match=typeerr):
                self.compile(
                    """
                    def dead_branch_type_error() -> None:
                        if False:
                            1 + "hello"
                    """,
                    error_mode="eager",
                )
            with SPyError.raises("W_TypeError", match=typeerr):
                self.compile(
                    """
                    def short_circuit_and_type_error() -> bool:
                        return False and (1 + "x")
                    """,
                    error_mode="eager",
                )
            with SPyError.raises("W_TypeError", match=typeerr):
                self.compile(
                    """
                    def short_circuit_or_type_error() -> bool:
                        return True or (1 + "x")
                    """,
                    error_mode="eager",
                )

    def test_assert_message_static_error_is_eager(self):
        src = """
        def assert_with_type_error_message(flag: bool) -> bool:
            assert flag, 1 + "x"
            return True
        """
        if self.backend == "interp":
            mod = self.compile(src, error_mode="eager")
            assert mod.assert_with_type_error_message(True) is True
            with SPyError.raises("W_TypeError", match=r"cannot do `i32` \+ `str`"):
                mod.assert_with_type_error_message(False)
        else:
            with SPyError.raises("W_TypeError", match=r"cannot do `i32` \+ `str`"):
                self.compile(src, error_mode="eager")

    @pytest.mark.parametrize("error_mode", ["lazy", "eager"])
    def test_static_error(self, error_mode):
        src = """
        @blue
        def get_message(lang):
            if lang == "en":
                return "hello"
            raise StaticError("unsupported lang: " + lang)

        def print_message(also_italian: i32) -> i32:
            print(get_message("en"))
            if also_italian:
                print(get_message("it"))
            return 42

        def foo() -> i32:
            return print_message(1)
        """

        if self.backend in ("doppler", "C") and error_mode == "eager":
            # eager errors and we are redshifting: expect a comptime error
            errors = expect_errors("unsupported lang: it")
            self.compile_raises(src, "foo", errors)
        else:
            # interp mode or lazy errors
            mod = self.compile(src, error_mode=error_mode)
            assert mod.print_message(0) == 42  # works
            with SPyError.raises("W_StaticError", match="unsupported lang: it"):
                mod.print_message(1)
