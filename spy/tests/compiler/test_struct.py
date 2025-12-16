from spy.errors import SPyError
from spy.fqn import FQN
from spy.tests.support import CompilerTest, expect_errors, only_interp
from spy.tests.wasm_wrapper import WasmPtr
from spy.vm.b import B
from spy.vm.modules.unsafe import UNSAFE
from spy.vm.modules.unsafe.ptr import W_Ptr
from spy.vm.object import W_Type
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

        def foo() -> Rect:
            r = make_rect(1, 2, 3, 4)
            return r
        """
        mod = self.compile(src)
        assert mod.foo() == ((1, 2), (3, 4))

    def test_method(self):
        src = """
        from math import sqrt

        @struct
        class Point:
            x: f64
            y: f64

            def hypot(self) -> f64:
                return sqrt(self.x * self.x + self.y * self.y)

        def foo(x: f64, y: f64) -> f64:
            p = Point(x, y)
            return p.hypot()

        def wrong_args(x: f64) -> f64:
            p = Point(x, x)
            return p.hypot(1, 2, 3)

        def wrong_meth(x: f64) -> f64:
            p = Point(x, x)
            return p.dont_exist()

        """
        mod = self.compile(src, error_mode="lazy")
        assert mod.foo(5.0, 12.0) == 13.0

        msg = "this function takes 1 argument but 4 arguments were supplied"
        with SPyError.raises("W_TypeError", match=msg):
            mod.wrong_args(10.0)

        msg = "method `test::Point::dont_exist` does not exist"
        with SPyError.raises("W_TypeError", match=msg):
            mod.wrong_meth(10.0)

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

    def test_class_body_bool_ops_declaration(self):
        src = """
        @struct
        class Flags:
            value: i32

            if True and False:
                def and_result(self) -> i32:
                    return 1
            else:
                def and_result(self) -> i32:
                    return 2

            if False or True:
                def or_result(self) -> i32:
                    return 3
            else:
                def or_result(self) -> i32:
                    return 4

        def read_and() -> i32:
            return Flags(0).and_result()

        def read_or() -> i32:
            return Flags(0).or_result()
        """
        mod = self.compile(src)
        assert mod.read_and() == 2
        assert mod.read_or() == 3

    def test_custom_eq(self):
        src = """
        @struct
        class Point:
            x: i32
            y: i32

            def __eq__(self, other: Point) -> bool:
                return self.x + self.y == other.x + other.y

        def foo(x0: i32, y0: i32, x1: i32, y1: i32) -> bool:
            p0 = Point(x0, y0)
            p1 = Point(x1, y1)
            return p0 == p1
        """
        mod = self.compile(src)
        assert mod.foo(1, 2, 3, 4) == False
        assert mod.foo(1, 2, 3, 0) == True

    @only_interp
    def test_dir(self):
        src = """
        from __spy__ import interp_list

        @struct
        class Point:
            x: i32
            y: i32

        def dir_type() -> interp_list[str]:
            return dir(Point)

        def dir_inst() -> interp_list[str]:
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

    def test_operator(self):
        mod = self.compile("""
        @struct
        class MyInt:
            __ll__: i32

            def __getitem__(m: MyInt, i: i32) -> i32:
                return m.__ll__ + i*2

        def foo(x: i32, y: i32) -> i32:
            m = MyInt(x)
            return m[y]
        """)
        assert mod.foo(30, 6) == 42

    def test_if_inside_classdef(self):
        src = """
        @blue
        def make_Foo(DOUBLE):
            @struct
            class Foo:
                __ll__: i32

                if DOUBLE:
                    def get(self) -> i32:
                        return self.__ll__ * 2
                else:
                    def get(self) -> i32:
                        return self.__ll__

            return Foo

        def test1(x: i32) -> i32:
            a = make_Foo(True)(x)
            return a.get()

        def test2(x: i32) -> i32:
            b = make_Foo(False)(x)
            return b.get()
        """
        mod = self.compile(src)
        assert mod.test1(10) == 20
        assert mod.test2(10) == 10

    def test_staticmethod(self):
        src = """
        from operator import OpSpec

        @struct
        class MyInt:
            __ll__: i32

            @staticmethod
            def one() -> MyInt:
                return MyInt.__make__(1)

            @staticmethod
            def from_pair(x: i32, y: i32) -> MyInt:
                return MyInt.__make__(x + y)

            @staticmethod
            @blue.metafunc
            def from_many(*args_m):
                if len(args_m) == 3:
                    def from3(x: i32, y: i32, z: i32) -> MyInt:
                        return MyInt.__make__(x + y + z)
                    return OpSpec(from3)
                raise TypeError('invalid number of args')

        def one() -> i32:
            m = MyInt.one()
            return m.__ll__

        def from_pair(x: i32, y: i32) -> i32:
            m = MyInt.from_pair(x, y)
            return m.__ll__

        def from_triple(x: i32, y: i32, z: i32) -> i32:
            m = MyInt.from_many(x, y, z)
            return m.__ll__

        def from_quadruple(x: i32, y: i32, z: i32, w: i32) -> i32:
            # this raises TypeError
            MyInt.from_many(x, y, z, w)
            return 9999 # never reached
        """
        mod = self.compile(src, error_mode="lazy")
        assert mod.one() == 1
        assert mod.from_pair(4, 5) == 9
        assert mod.from_triple(4, 5, 6) == 15
        with SPyError.raises("W_TypeError", match="invalid number of args"):
            mod.from_quadruple(4, 5, 6, 7)

    def test_property(self):
        src = """
        @struct
        class Point:
            x: i32
            y: i32

            @property
            def xy(self) -> i32:
                return self.x + self.y

        def foo(x: i32, y: i32) -> i32:
            p = Point(x, y)
            return p.xy
        """
        mod = self.compile(src)
        assert mod.foo(3, 4) == 7

    def test_fwdecl_is_ignored_by_C_backend(self):
        src = """
        @blue
        def make_point_maybe(make_it: bool):
            if not make_it:
                return

            @struct
            class Point:
                x: i32
                y: i32

        def foo() -> i32:
            make_point_maybe(False)
            return 42
        """
        # make_point_maybe::Point is declared unconditionally just by entering
        # make_point_maybe(), even if it's never used. The point of the test is to
        # ensure that the C backend knows how to deal with it and doesn't crash.
        mod = self.compile(src)
        assert mod.foo() == 42
        w_Point = self.vm.lookup_global(FQN("test::make_point_maybe::Point"))
        assert isinstance(w_Point, W_Type)
        assert not w_Point.is_defined()  # it's a fwdecl
