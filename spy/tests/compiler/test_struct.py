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

    def test_nested_struct(self):
        src = """
        @struct
        class Point:
            x: i32
            y: i32

        @struct
        class Rect:
            a: Point
            b: Point

        def make_rect(x0: i32, y0: i32, x1: i32, y1: i32) -> Rect:
            return Rect(Point(x0, y0), Point(x1, y1))

        def foo() -> i32:
            r = make_rect(1, 2, 3, 4)
            return r.a.x + 10*r.a.y + 100*r.b.x + 1000*r.b.y
        """
        mod = self.compile(src)
        assert mod.foo() == 4321

    def test_method(self):
        src = """
        from math import sqrt

        @struct
        class Point:
            x: f64
            y: f64

            def hypot(self: Point) -> f64:
                return sqrt(self.x * self.x + self.y * self.y)

        def foo(x: f64, y: f64) -> f64:
            p = Point(x, y)
            return p.hypot()
        """
        mod = self.compile(src)
        assert mod.foo(5.0, 12.0) == 13.0
