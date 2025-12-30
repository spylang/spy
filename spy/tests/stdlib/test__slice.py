from spy.tests.support import CompilerTest, only_interp
from spy.vm.struct import UnwrappedStruct


class TestSlice(CompilerTest):
    @only_interp
    def test__slice_module(self):
        src = """
        from _slice import Slice

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
