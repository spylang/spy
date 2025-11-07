# -*- encoding: utf-8 -*-

from spy.errors import SPyError
from spy.fqn import FQN
from spy.tests.support import CompilerTest, expect_errors, only_interp
from spy.tests.wasm_wrapper import WasmPtr
from spy.vm.b import B
from spy.vm.modules.unsafe import UNSAFE
from spy.vm.modules.unsafe.ptr import W_Ptr
from spy.vm.struct import UnwrappedStruct


def test_UnwrappedStruct():
    us1 = UnwrappedStruct(FQN("test::Point"), {"x": 1, "y": 2})
    us2 = UnwrappedStruct(FQN("test::Point"), {"x": 1, "y": 2})
    us3 = UnwrappedStruct(FQN("test::Point"), {"x": 3, "y": 4})
    us4 = UnwrappedStruct(FQN("aaaa::bbbbb"), {"x": 1, "y": 2})
    assert us1 == us2
    assert us1 != us3
    assert us1 != us4
    assert us1 == (1, 2)


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

    def test_wrong_field(self):
        src = """
        @struct
        class Point:
            x: i32
            y: i32

        def foo() -> i32:
            p = Point(0, 0)
            return p.z
        """
        errors = expect_errors(
            "type `test::Point` has no attribute 'z'",
            ("this is `test::Point`", "p"),
            ("`p` defined here", "p"),
        )
        self.compile_raises(src, "foo", errors)

    def test_spy_unwrap(self):
        src = """
        @struct
        class Point:
            x: i32
            y: i32

        def make_point(x: i32, y: i32) -> Point:
            return Point(x, y)

        def get_x(p: Point) -> i32:
            return p.x
        """
        mod = self.compile(src)
        p = mod.make_point(1, 2)
        assert p == (1, 2)
        assert mod.get_x(p) == 1

    def test_pass_and_return(self):
        src = """
        @struct
        class Point:
            x: i32
            y: i32

        def move(p: Point, delta: i32) -> Point:
            return Point(p.x + delta, p.y + delta)

        def foo(x: i32, y: i32) -> Point:
            p = Point(x, y)
            return move(p, 3)
        """
        mod = self.compile(src)
        assert mod.foo(1, 2) == (4, 5)

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
            ("this is `test::Point`", "p"),
            ("`p` defined here", "p: Point"),
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

    def test_custom_new(self):
        src = """
        @struct
        class Point:
            x: i32
            y: i32

            def __new__() -> Point:
                return Point.__make__(0, 0)

        def foo() -> Point:
            return Point()
        """
        mod = self.compile(src)
        assert mod.foo() == (0, 0)

    @only_interp
    def test_dir(self):
        src = """
        @struct
        class Point:
            x: i32
            y: i32

        def dir_type() -> list[str]:
            return dir(Point)

        def dir_inst() -> list[str]:
            p = Point(1, 2)
            return dir(p)
        """
        mod = self.compile(src)
        dt = mod.dir_type()
        assert "__str__" in dt
        assert "__make__" in dt
        assert "x" in dt
        assert "y" in dt

        di = mod.dir_inst()
        assert "__str__" in di
        assert "__make__" in di
        assert "x" in di
        assert "y" in di
