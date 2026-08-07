import pytest

from spy.tests.support import CompilerTest, only_native


@only_native
class TestNative(CompilerTest):
    def test_call_order(self):
        # see also the related TestLinearize.test_call_order.
        #
        # In C, call order is not specified. This test happened to pass "by chance" when
        # compiled to WASM (the default for the C backend), but to fail when compiled to
        # x86_64, which is what we test here.
        src = """
        def foo() -> i32:
            print("foo")
            return 10

        def bar() -> i32:
            print("bar")
            return 3

        def sub(a: i32, b: i32) -> i32:
            return a - b

        def main() -> None:
            res = sub(foo(), bar())
            print(res)
        """
        exe = self.compile(src)
        out = exe.run()
        lines = out.splitlines()
        assert lines == ["foo", "bar", "7"]
