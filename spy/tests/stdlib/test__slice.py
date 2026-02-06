from textwrap import dedent

from spy.tests.support import CompilerTest, only_interp
from spy.vm.struct import UnwrappedStruct


class TestSlice(CompilerTest):
    def test__slice_module(self):
        src = """
        def make_slice() -> slice:
            return slice(0,1,2)

        def make_slice_none() -> slice:
            return slice(None, None, None)
        """
        mod = self.compile(src)
        s = mod.make_slice()
        assert type(s) == UnwrappedStruct
        assert "_slice::Slice" in str(s.fqn)
        assert (s.start, s.stop, s.step) == (0, 1, 2)
        assert (s.start_is_none, s.stop_is_none, s.step_is_none) == (0, 0, 0)

        sn = mod.make_slice_none()
        assert type(s) == UnwrappedStruct
        assert "_slice::Slice" in str(s.fqn)
        assert (sn.start_is_none, sn.stop_is_none, sn.step_is_none) == (1, 1, 1)

    def test__slice_indices(self):
        # This test is a bit of a workaround for the fact that we cannot easily
        # have SPy functions which accept either int or None; and we want to test a
        # bunch of different combinations of int and None args against the
        # Slice.indices() function to make sure the results come out right.
        #
        # So instead, we generate the source of all the functions we want to test
        # (using the naming function below) so that we can call them from the
        # test with no arguments

        def args_to_func_name(*args: int | None) -> str:
            return "f" + "_".join(str(a).replace("-", "n") for a in args)

        # For each pair (inp, out), it should be true that slice(*inp).indices() == out
        # These test cases replicate those in CPython
        type i_N = int | None
        eq_list: list[tuple[tuple[i_N, i_N, i_N, int], tuple[int, int, int]]] = [
            ((None, None, None, 10), (0, 10, 1)),
            ((None, None, 2, 10), (0, 10, 2)),
            ((1, None, 2, 10), (1, 10, 2)),
            ((None, None, -1, 10), (9, -1, -1)),
            ((None, None, -2, 10), (9, -1, -2)),
            ((3, None, -2, 10), (3, -1, -2)),
            # CPython issue 3004 tests
            ((None, -9, None, 10), (0, 1, 1)),
            ((None, -10, None, 10), (0, 0, 1)),
            ((None, -11, None, 10), (0, 0, 1)),
            ((None, -10, -1, 10), (9, 0, -1)),
            ((None, -11, -1, 10), (9, -1, -1)),
            ((None, -12, -1, 10), (9, -1, -1)),
            ((None, 9, None, 10), (0, 9, 1)),
            ((None, 10, None, 10), (0, 10, 1)),
            ((None, 11, None, 10), (0, 10, 1)),
            ((None, 8, -1, 10), (9, 8, -1)),
            ((None, 9, -1, 10), (9, 9, -1)),
            ((None, 10, -1, 10), (9, 9, -1)),
            ((-100, 100, None, 10), (0, 10, 1)),
        ]

        src = "from _slice import tuple3"

        # Generate a function (who's name we know) that takes no arguments
        # and returns the slice.indices() of the given slice.
        # Append that function to the source code for the module
        # we're about to compile.
        for inp, _ in eq_list:
            src += dedent(f"""
            def {args_to_func_name(*inp)}() -> tuple3:
                s: slice = slice({inp[0]}, {inp[1]}, {inp[2]})
                return s.indices({inp[3]})
            """)

        mod = self.compile(src)

        for inp, out in eq_list:
            # For each pair (inp, out), it should be true that slice(*inp).indices() == out
            assert getattr(mod, args_to_func_name(*inp))() == out
        return
