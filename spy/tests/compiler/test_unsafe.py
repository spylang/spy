#-*- encoding: utf-8 -*-

import pytest
from spy.errors import SPyPanicError
from spy.tests.support import CompilerTest, no_C, expect_errors

class TestUnsafe(CompilerTest):

    def test_gc_alloc(self):
        mod = self.compile(
        """
        from unsafe import gc_alloc, ptr

        def foo() -> i32:
            # XXX: ideally we want gc_alloc[i32](1), but we can't for now
            #
            # XXX: ideally we would like the type of "buf" to be inferrable
            # but we can't for now because the return type of
            # gc_alloc(i32)(...) is `dynamic`
            #
            buf: ptr[i32] = gc_alloc(i32)(1)
            buf[0] = 42
            return buf[0]

        def bar(i: i32) -> f64:
            # make sure that we can use other item types as well
            buf: ptr[f64] = gc_alloc(f64)(3)
            buf[0] = 1.2
            buf[1] = 3.4
            buf[2] = 5.6
            return buf[i]
        """)
        assert mod.foo() == 42
        assert mod.bar(0) == 1.2
        assert mod.bar(1) == 3.4
        assert mod.bar(2) == 5.6

    def test_out_of_bound(self):
        mod = self.compile(
        """
        from unsafe import gc_alloc, ptr

        def foo(i: i32) -> i32:
            buf: ptr[i32] = gc_alloc(i32)(3)
            buf[0] = 0
            buf[1] = 100
            buf[2] = 200
            return buf[i]
        """)
        assert mod.foo(1) == 100
        with pytest.raises(SPyPanicError, match="ptr_load out of bounds"):
            mod.foo(3)

    def test_struct(self):
        mod = self.compile(
        """
        from unsafe import gc_alloc, ptr

        class Point(struct):
            x: i32
            y: f64

        def make_point(x: i32, y: f64) -> ptr[Point]:
            p: ptr[Point] = gc_alloc(Point)(1)
            p.x = x
            p.y = y
            return p

        def foo(x: i32, y: f64) -> f64:
            p = make_point(x, y)
            return p.x + p.y
        """)
        assert mod.foo(3, 4.5) == 7.5

    def test_struct_wrong_field(self):
        src = """
        from unsafe import ptr, gc_alloc

        # XXX we should remove this workaround: currently you can use 'i32'
        # inside 'class Point' only if 'i32' is used somewhere else at the
        # module level.
        WORKAROUND: i32 = 0

        class Point(struct):
            x: i32
            y: i32

        def foo() -> void:
            p: ptr[Point] = gc_alloc(Point)(1)
            p.z = 42
        """
        errors = expect_errors(
            "type `unsafe::ptr[test::Point]` does not support assignment to attribute 'z'",
            ('this is `unsafe::ptr[test::Point]`', 'p'),
        )
        self.compile_raises(src, 'foo', errors)

    def test_nested_struct(self):
        mod = self.compile(
        """
        from unsafe import gc_alloc, ptr

        class Point(struct):
            x: i32
            y: i32

        class Rect(struct):
            a: Point
            b: Point

        def make_rect(x0: i32, y0: i32, x1: i32, y1: i32) -> ptr[Rect]:
            r: ptr[Rect] = gc_alloc(Rect)(1)

            # write via ptr
            r_a: ptr[Point] = r.a
            r_a.x = x0
            r_a.y = y0

            # write via chained fields
            r.b.x = x1
            r.b.y = y1
            return r

        def foo() -> i32:
            r = make_rect(1, 2, 3, 4)
            return r.a.x + 10*r.a.y + 100*r.b.x + 1000*r.b.y
        """)
        assert mod.foo() == 4321

    def test_ptr_eq(self):
        mod = self.compile("""
        from unsafe import gc_alloc, ptr

        def alloc() -> ptr[i32]:
            return gc_alloc(i32)(1)

        def eq(a: ptr[i32], b: ptr[i32]) -> bool:
            return a == b

        def ne(a: ptr[i32], b: ptr[i32]) -> bool:
            return a != b
        """)
        p0 = mod.alloc()
        p1 = mod.alloc()
        assert mod.eq(p0, p0)
        assert not mod.eq(p0, p1)
        assert not mod.ne(p0, p0)
        assert mod.ne(p0, p1)
