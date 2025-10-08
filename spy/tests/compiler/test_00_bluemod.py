import textwrap
from typing import Any

import pytest

from spy.backend.interp import InterpModuleWrapper
from spy.vm.b import B
from spy.vm.function import W_ASTFunc, W_FuncType
from spy.vm.vm import SPyVM


@pytest.mark.usefixtures("init")
class TestBlueMod:
    @pytest.fixture
    def init(self, tmpdir):
        self.tmpdir = tmpdir
        self.vm = SPyVM()
        self.vm.path.append(str(tmpdir))

    def write_file(self, filename: str, src: str) -> Any:
        """
        Write the give source code to the specified filename, in the tmpdir.

        The source code is automatically dedented.
        """
        src = textwrap.dedent(src)
        srcfile = self.tmpdir.join(filename)
        srcfile.write(src)
        return srcfile

    def import_(self, src: str) -> Any:
        self.write_file("test.spy", src)
        w_mod = self.vm.import_("test")
        return InterpModuleWrapper(self.vm, w_mod)

    def test_simple(self):
        mod = self.import_("""
        @blue
        def foo():
            return 42
        """)
        assert mod.foo() == 42

    def test_param(self):
        mod = self.import_("""
        @blue
        def foo(x):
            return x
        """)
        assert mod.foo(53) == 53

    def test_load_global(self):
        mod = self.import_("""
        @blue
        def foo():
            return i32
        """)
        w_mod = mod.w_mod
        w_foo = w_mod.getattr("foo")
        w_res = self.vm.fast_call(w_foo, [])
        assert w_res is B.w_i32

    def test_make_function(self):
        mod = self.import_("""
        @blue
        def foo():
            def bar(x: i32) -> i32:
                return x
            return bar
        """)
        w_mod = mod.w_mod
        w_foo = w_mod.getattr("foo")
        w_bar = self.vm.fast_call(w_foo, [])
        assert isinstance(w_bar, W_ASTFunc)
        assert w_bar.w_functype == W_FuncType.parse("def(i32) -> i32")
        w_42 = self.vm.wrap(42)
        assert self.vm.fast_call(w_bar, [w_42]) is w_42

    def test_closure(self):
        mod = self.import_("""
        @blue
        def make_adder(x):
            def adder(y: i32) -> i32:
                return x+y
            return adder
        """)
        w_mod = mod.w_mod
        w_make_adder = w_mod.getattr("make_adder")
        w_add5 = self.vm.fast_call(w_make_adder, [self.vm.wrap(5)])
        assert isinstance(w_add5, W_ASTFunc)
        w_42 = self.vm.fast_call(w_add5, [self.vm.wrap(37)])
        res = self.vm.unwrap(w_42)
        assert res == 42
