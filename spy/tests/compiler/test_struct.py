#-*- encoding: utf-8 -*-

from spy.errors import SPyError
from spy.vm.b import B
from spy.vm.modules.unsafe import UNSAFE
from spy.vm.modules.unsafe.ptr import W_Ptr
from spy.tests.wasm_wrapper import WasmPtr
from spy.tests.support import CompilerTest, expect_errors, only_interp

class TestStructOnStack(CompilerTest):
    """
    Test for structs allocated on the stack, passed around by value as
    primitive types.

    There are additional tests for ptr-to-structs in test_unsafe.py.
    """

    def test_simple(self):
        src = """
        @struct
        class Point:
            x: i32
            y: i32

        def foo(x: i32, y: i32) -> i32:
            p = Point(x, y)
            return p.x + p.y

        def bar(x: i32, y: i32) -> i32:
            p = Point.__make__(x, y)
            return p.x + p.y
        """
        mod = self.compile(src)
        assert mod.foo(3, 4) == 7
        assert mod.bar(5, 6) == 11

    def test_pass_and_return(self):
        src = """
        @struct
        class Point:
            x: i32
            y: i32

        def move(p: Point, delta: i32) -> Point:
            return Point(p.x + delta, p.y + delta)

        def foo(x: i32, y: i32) -> i32:
            p = Point(x, y)
            p2 = move(p, 3)
            return p2.x + p2.y
        """
        mod = self.compile(src)
        assert mod.foo(1, 2) == (1+3) + (2+3)

    def test_cannot_mutate(self):
        src = """
        @struct
        class Point:
            x: i32
            y: i32

        def mutate(p: Point) -> None:
            p.x = 0

        def foo() -> None:
            p = Point(1, 2)
            mutate(p)
        """
        errors = expect_errors(
            "type `test::Point` does not support assignment to attribute 'x'",
            ('this is `test::Point`', 'p'),
            ('`p` defined here', 'p: Point'),
        )
        self.compile_raises(src, "foo", errors)
