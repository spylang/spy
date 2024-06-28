import pytest
from spy.llwasm import LLWasmInstance
from spy.cbuild import get_toolchain
from spy.tests.support import CTest

class TestToolchain(CTest):

    @pytest.mark.parametrize("toolchain", ["zig", "clang"])
    def test_c2wasm(self, toolchain):
        self.toolchain = get_toolchain(toolchain)
        src = r"""
        int add(int x, int y) {
            return x+y;
        }
        """
        test_wasm = self.compile(src, exports=['add'])
        ll = LLWasmInstance.from_file(test_wasm)
        assert ll.call('add', 4, 8) == 12
