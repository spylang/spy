import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest, expect_errors, no_C


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
        loc = excinfo.value.w_exc.annotations[0].loc
        assert loc.filename == str(self.tmpdir.join("test.spy"))
        assert loc.line_start == 6

        with SPyError.raises("W_ValueError", match="world"):
            mod.foo(2)
        with SPyError.raises("W_ValueError", match=""):
            mod.foo(3)
        with SPyError.raises("W_IndexError") as excinfo:
            mod.foo(4)

    def test_cannot_raise_red(self):
        src = """
        def foo() -> None:
            exc = Exception("hello")
            raise exc
        """
        errors = expect_errors(
            "`raise` only accepts blue values for now",
            ("this is red", "exc"),
            )
        self.compile_raises(src, "foo", errors)

    def test_lazy_error(self):
        src = """
        def foo() -> None:
            1 + "hello"
        """
        mod = self.compile(src, error_mode="lazy")
        with SPyError.raises("W_TypeError", match=r"cannot do `i32` \+ `str`"):
            mod.foo()

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
            assert mod.print_message(0) == 42 # works
            with SPyError.raises("W_StaticError", match="unsupported lang: it"):
                mod.print_message(1)

    @no_C
    def test_add_location_if_missing(self):
        mod = self.compile("""
        from _testing_helpers import raise_no_loc

        def foo() -> None:
            raise_no_loc()
        """)

        errors = expect_errors(
            "this is some error",
            ("called from here", "raise_no_loc()"),
            )
        with errors:
            mod.foo()

    def test_add_location_to_stmt(self):
        # here we test that we add _some_ location info to SPyErrors generated
        # while executing ASTFrame.exec_stmt(). However, it's not trivial to
        # write a test, becuase most stmt don't raise at all.
        #
        # The trick is to abuse what happens inside the @struct decorator,
        # which is indirectly called by exec_stmt_ClassDef: at the moment of
        # writing, it raises a WIP with bool fields, so we can use that. When
        # we implement bool fields, we will need to find another way to
        # generate a raise.
        src = """
        @struct
        class X:
            flag: bool
        """

        errors = expect_errors(
            "sizeof(<spy type 'bool'>) not implemented",
            ("called from here", "class X:\n    flag: bool"),
            )
        with errors:
            self.compile(src)
