import itertools
from random import randint

from spy.tests.support import CompilerTest, only_interp
from spy.vm.struct import UnwrappedStruct


class TestSlice(CompilerTest):
    def test__slice_module(self):
        src = """
        def make_slice() -> Slice:
            return Slice(0,1,2)

        def make_slice_none() -> Slice:
            return Slice(None, None, None)
        """
        mod = self.compile(src)
        s = mod.make_slice()
        assert type(s) == UnwrappedStruct
        assert "_slice::Slice" in str(s.fqn)
        assert (s.start, s.stop, s.step) == (0, 1, 2)
        assert not any([s.start_is_none, s.stop_is_none, s.step_is_none])

        sn = mod.make_slice_none()
        assert type(s) == UnwrappedStruct
        assert "_slice::Slice" in str(s.fqn)
        assert all([sn.start_is_none, sn.stop_is_none, sn.step_is_none])

    def test__slice_indices(self):
        def get_slice_indices(
            start=None, stop=None, step=None, *, length
        ) -> tuple[int, int, int]:
            src = f"""
                def _get_indices() -> str:
                    s: Slice = Slice({start}, {stop}, {step})
                    indices = s.indices({length})
                    return str(indices.start) + ", " + str(indices.stop) + ", " + str(indices.step)
            """
            mod = self.compile(
                src,
                f"slicetest{'_'.join(str(s).replace('-', 'n') for s in (start, stop, step))}",
            )  # Modules must have unique names or they won't be reimported by the vm
            result = mod._get_indices()
            return result

        assert get_slice_indices(None, length=10) == "0, 10, 1"
        assert get_slice_indices(None, None, 2, length=10) == "0, 10, 2"
        assert get_slice_indices(1, None, 2, length=10) == "1, 10, 2"
        assert get_slice_indices(None, None, -1, length=10) == "9, -1, -1"
        assert get_slice_indices(None, None, -2, length=10) == "9, -1, -2"
        assert get_slice_indices(3, None, -2, length=10) == "3, -1, -2"
        # issue 3004 tests
        assert get_slice_indices(None, -9, length=10) == "0, 1, 1"
        assert get_slice_indices(None, -10, length=10) == "0, 0, 1"
        assert get_slice_indices(None, -11, length=10) == "0, 0, 1"
        assert get_slice_indices(None, -10, -1, length=10) == "9, 0, -1"
        assert get_slice_indices(None, -11, -1, length=10) == "9, -1, -1"
        assert get_slice_indices(None, -12, -1, length=10) == "9, -1, -1"
        assert get_slice_indices(None, 9, length=10) == "0, 9, 1"
        assert get_slice_indices(None, 10, length=10) == "0, 10, 1"
        assert get_slice_indices(None, 11, length=10) == "0, 10, 1"
        assert get_slice_indices(None, 8, -1, length=10) == "9, 8, -1"
        assert get_slice_indices(None, 9, -1, length=10) == "9, 9, -1"
        assert get_slice_indices(None, 10, -1, length=10) == "9, 9, -1"

        assert get_slice_indices(-100, 100, length=10) == get_slice_indices(
            None, length=10
        )
        assert get_slice_indices(100, -100, -1, length=10) == get_slice_indices(
            None, None, -1, length=10
        )

        assert get_slice_indices(-100, 100, 2, length=10) == "0, 10, 2"
