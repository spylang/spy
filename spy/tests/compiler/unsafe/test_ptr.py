import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest, expect_errors, only_C, only_interp
from spy.tests.wasm_wrapper import WasmPtr
from spy.vm.b import B
from spy.vm.modules.unsafe import UNSAFE
from spy.vm.modules.unsafe.ptr import W_Ptr


@pytest.fixture(params=["raw", "gc"])
def memkind(request):
    return request.param


class TestUnsafePtr(CompilerTest):
    @only_interp
    def test_ptrtype_repr(self):
        w_raw_ptrtype = self.vm.fast_call(UNSAFE.w_raw_ptr, [B.w_i32])
        w_raw_reftype = self.vm.fast_call(UNSAFE.w_raw_ref, [B.w_i32])
        w_gc_ptrtype = self.vm.fast_call(UNSAFE.w_gc_ptr, [B.w_i32])
        w_gc_reftype = self.vm.fast_call(UNSAFE.w_gc_ref, [B.w_i32])
        assert repr(w_raw_ptrtype) == "<spy type 'unsafe::raw_ptr[i32]'>"
        assert repr(w_raw_reftype) == "<spy type 'unsafe::raw_ref[i32]'>"
        assert repr(w_gc_ptrtype) == "<spy type 'unsafe::gc_ptr[i32]'>"
        assert repr(w_gc_reftype) == "<spy type 'unsafe::gc_ref[i32]'>"

    @only_interp
    def test_itemtype(self):
        mod = self.compile("""
        from unsafe import raw_ptr, raw_ref

        def get_itemtype_ptr() -> type:
            return raw_ptr[i32].itemtype

        def get_itemtype_ref() -> type:
            return raw_ref[f64].itemtype
        """)
        w_T = mod.get_itemtype_ptr(unwrap=False)
        assert w_T is B.w_i32
        w_T = mod.get_itemtype_ref(unwrap=False)
        assert w_T is B.w_f64

    def test_alloc(self, memkind):
        k = memkind
        mod = self.compile(f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr

        def foo() -> i32:
            buf: k_ptr[i32] = k_alloc[i32](1)
            buf[0] = 42
            return buf[0]

        def bar(i: i32) -> f64:
            # make sure that we can use other item types as well
            buf = k_alloc[f64](3)
            buf[0] = 1.2
            buf[1] = 3.4
            buf[2] = 5.6
            return buf[i]
        """)
        assert mod.foo() == 42
        assert mod.bar(0) == 1.2
        assert mod.bar(1) == 3.4
        assert mod.bar(2) == 5.6

    def test_out_of_bound(self, memkind):
        k = memkind
        mod = self.compile(f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr

        def foo(i: i32) -> i32:
            buf = k_alloc[i32](3)
            buf[0] = 0
            buf[1] = 100
            buf[2] = 200
            return buf[i]

        def bar(i: i32, v: i32) -> i32:
            buf = k_alloc[i32](3)
            buf[0] = 0
            buf[1] = 100
            buf[2] = 200
            buf[i] = v
            return buf[i]
        """)
        assert mod.foo(1) == 100
        assert mod.bar(1, 50) == 50
        with SPyError.raises("W_PanicError", match="ptr_getitem out of bounds"):
            mod.foo(3)
        with SPyError.raises("W_PanicError", match="ptr_store out of bounds"):
            mod.bar(3, 300)
        with SPyError.raises("W_PanicError", match="ptr_getitem out of bounds"):
            mod.foo(-2)
        with SPyError.raises("W_PanicError", match="ptr_store out of bounds"):
            mod.bar(-5, 300)

    def test_ptr_to_struct(self, memkind):
        k = memkind
        mod = self.compile(f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, {k}_ref as k_ref

        @struct
        class Point:
            x: i32
            y: f64

        def make_point(x: i32, y: f64) -> k_ptr[Point]:
            p = k_alloc[Point](1)
            p.x = x
            p.y = y
            return p

        def with_ptr(x: i32, y: f64) -> f64:
            p = make_point(x, y)
            return p.x + p.y

        def with_ref(x: i32, y: f64) -> f64:
            # reading an item out of a ptr returns a ref
            p = make_point(x, y)
            r: k_ref[Point] = p[0]
            return r.x + r.y

        """)
        assert mod.with_ptr(3, 4.5) == 7.5
        assert mod.with_ref(6, 7.8) == 13.8

    def test_ptr_to_string(self, memkind):
        # XXX: support for raw_alloc[str] was added by 30ffdb9a, but doesn't make sense
        # now. We should support ONLY gc_alloc[str]
        k = memkind
        mod = self.compile(f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr

        def make_str_ptr(s: str) -> k_ptr[str]:
            p = k_alloc[str](1)
            p[0] = s
            return p

        def foo() -> str:
            p = make_str_ptr("hello")
            return p[0]
        """)
        assert mod.foo() == "hello"

    @only_interp
    def test_dir(self, memkind):
        k = memkind
        mod = self.compile(f"""
        from __spy__ import interp_list
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr

        @struct
        class Point:
            x: i32
            y: i32

        def dir_ptr_point() -> interp_list[str]:
            p = k_alloc[Point](1)
            return dir(p)

        def dir_ref_point() -> interp_list[str]:
            p = k_alloc[Point](1)
            r = p[0]
            return dir(r)

        """)
        d1 = mod.dir_ptr_point()
        assert "x" in d1
        assert "y" in d1

        d2 = mod.dir_ref_point()
        assert "x" in d2
        assert "y" in d2

    def test_struct_wrong_field(self, memkind):
        k = memkind
        src = f"""
        from unsafe import {k}_ptr as k_ptr, {k}_alloc as k_alloc

        @struct
        class Point:
            x: i32
            y: i32

        def set_z_ptr() -> None:
            p = k_alloc[Point](1)
            p.z = 42

        def set_z_ref() -> None:
            p = k_alloc[Point](1)
            r = p[0]
            r.z = 42
        """
        mod = self.compile(src, error_mode="lazy")
        errors = expect_errors(
            f"type `unsafe::{k}_ptr[test::Point]` does not support "
            + "assignment to attribute 'z'",
        )
        with errors:
            mod.set_z_ptr()

        errors = expect_errors(
            f"type `unsafe::{k}_ref[test::Point]` does not support "
            + "assignment to attribute 'z'",
        )
        with errors:
            mod.set_z_ref()

    def test_nested_struct(self, memkind):
        k = memkind
        mod = self.compile(f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, {k}_ref as k_ref

        @struct
        class Point:
            x: i32
            y: i32

        @struct
        class Rect:
            a: Point
            b: Point

        def make_rect_ptr(x0: i32, y0: i32, x1: i32, y1: i32) -> k_ptr[Rect]:
            r: k_ptr[Rect] = k_alloc[Rect](1)

            # write via ref
            r_a: k_ref[Point] = r.a
            r_a.x = x0
            r_a.y = y0

            # write via chained fields
            r.b.x = x1
            r.b.y = y1
            return r

        def make_rect_ref(x0: i32, y0: i32, x1: i32, y1: i32) -> k_ref[Rect]:
            p = k_alloc[Rect](1)
            r: k_ref[Rect] = p[0]

            # write via ref
            r_a: k_ref[Point] = r.a
            r_a.x = x0
            r_a.y = y0

            # write via chained fields
            r.b.x = x1
            r.b.y = y1
            return r

        def rect_ptr() -> i32:
            p: k_ptr[Rect] = make_rect_ptr(1, 2, 3, 4)
            return p.a.x + 10*p.a.y + 100*p.b.x + 1000*p.b.y

        def rect_ref() -> i32:
            r: k_ref[Rect] = make_rect_ref(6, 7, 8, 9)
            return r.a.x + 10*r.a.y + 100*r.b.x + 1000*r.b.y
        """)
        assert mod.rect_ptr() == 4321
        assert mod.rect_ref() == 9876

    def test_ptr_eq(self, memkind):
        k = memkind
        mod = self.compile(f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr

        def alloc() -> k_ptr[i32]:
            return k_alloc[i32](1)

        def eq(a: k_ptr[i32], b: k_ptr[i32]) -> bool:
            return a == b

        def ne(a: k_ptr[i32], b: k_ptr[i32]) -> bool:
            return a != b
        """)
        p0 = mod.alloc()
        p1 = mod.alloc()
        assert mod.eq(p0, p0)
        assert not mod.eq(p0, p1)
        assert not mod.ne(p0, p0)
        assert mod.ne(p0, p1)

    def test_ref_eq(self, memkind):
        k = memkind
        mod = self.compile(f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, {k}_ref as k_ref

        @struct
        class MyInt:
            val: i32

        def alloc() -> k_ptr[MyInt]:
            return k_alloc[MyInt](1)

        def eq(a: k_ptr[MyInt], b: k_ptr[MyInt]) -> bool:
            ra: k_ref[MyInt] = a[0]
            rb: k_ref[MyInt] = b[0]
            return ra == rb

        def ne(a: k_ptr[MyInt], b: k_ptr[MyInt]) -> bool:
            ra: k_ref[MyInt] = a[0]
            rb: k_ref[MyInt] = b[0]
            return ra != rb
        """)
        p0 = mod.alloc()
        p1 = mod.alloc()
        assert mod.eq(p0, p0)
        assert not mod.eq(p0, p1)
        assert not mod.ne(p0, p0)
        assert mod.ne(p0, p1)

    def test_can_allocate_ptr(self, memkind):
        k = memkind
        mod = self.compile(f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr

        @struct
        class Array:
            n: i32
            buf: k_ptr[i32]

        def foo(i: i32) -> i32:
            arr = k_alloc[Array](1)
            arr.n = 3
            arr.buf = k_alloc[i32](4)
            arr.buf[0] = 1
            arr.buf[1] = 2
            arr.buf[2] = 3
            return arr.buf[i]
        """)
        assert mod.foo(2) == 3

    def test_generic_struct(self, memkind):
        k = memkind
        mod = self.compile(f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr

        @blue
        def make_Point(T):
            @struct
            class Point:
                x: T
                y: T
            return Point

        Point_i32 = make_Point(i32)
        Point_f64 = make_Point(f64)

        def foo() -> i32:
            p = k_alloc[Point_i32](1)
            p.x = 1
            p.y = 2
            return p.x + p.y

        def bar() -> f64:
            p = k_alloc[Point_f64](1)
            p.x = 1.2
            p.y = 3.4
            return p.x + p.y
        """)
        assert mod.foo() == 3
        assert mod.bar() == 4.6

    def test_ptr_NULL(self, memkind):
        k = memkind
        mod = self.compile(f"""
        from unsafe import {k}_ptr as k_ptr

        def foo() -> k_ptr[i32]:
            return k_ptr[i32].NULL
        """)
        w_p = mod.foo()
        if self.backend in ("interp", "doppler"):
            assert isinstance(w_p, W_Ptr)
            assert w_p.addr == 0
            assert w_p.length == 0
            assert repr(w_p) == f"W_Ptr('{k}', i32, NULL)"
        else:
            assert isinstance(w_p, WasmPtr)
            assert w_p.addr == 0
            assert w_p.length == 0

    @only_C
    def test_ptr_NULL_check(self, memkind):
        k = memkind
        mod = self.compile(f"""
        from unsafe import {k}_ptr as k_ptr

        null_ptr: k_ptr[i32] = k_ptr[i32].NULL

        def foo(i: i32) -> i32:
            return null_ptr[i]

        def bar(i: i32, v: i32) -> None:
            null_ptr[i] = v
        """)
        with SPyError.raises("W_PanicError", "cannot dereference NULL pointer"):
            mod.foo(1)
        with SPyError.raises("W_PanicError", "cannot dereference NULL pointer"):
            mod.bar(1, 10)

    def test_NULL_in_global(self, memkind):
        k = memkind
        mod = self.compile(f"""
        from unsafe import {k}_ptr as k_ptr

        global_ptr: k_ptr[i32] = k_ptr[i32].NULL

        def is_null() -> bool:
            return global_ptr == k_ptr[i32].NULL
        """)
        assert mod.is_null() is True

    def test_ptr_truth(self, memkind):
        k = memkind
        mod = self.compile(f"""
        from unsafe import {k}_ptr as k_ptr, {k}_alloc as k_alloc

        def is_null(p: k_ptr[i32]) -> bool:
            if p:
                return False
            else:
                return True

        def foo() -> bool:
            return is_null(k_ptr[i32].NULL)

        def bar() -> bool:
            p = k_alloc[i32](1)
            return is_null(p)

        """)
        assert mod.foo() is True
        assert mod.bar() is False

    def test_struct_with_ptr_to_itself(self, memkind, capfd):
        k = memkind
        mod = self.compile(f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr

        @struct
        class Node:
            val: i32
            next: k_ptr[Node]

        def new_node(val: i32) -> k_ptr[Node]:
            n = k_alloc[Node](1)
            n.val = val
            n.next = k_ptr[Node].NULL
            return n

        def alloc_list(a: i32, b: i32, c: i32) -> k_ptr[Node]:
            lst = new_node(a)
            lst.next = new_node(b)
            lst.next.next = new_node(c)
            return lst

        def print_list(n: k_ptr[Node]) -> None:
            if n:
                print(n.val)
                print_list(n.next)
        """)
        ptr = mod.alloc_list(1, 2, 3)
        mod.print_list(ptr)
        if self.backend == "C":
            mod.ll.call("spy_flush")
        out, err = capfd.readouterr()
        assert out.splitlines() == ["1", "2", "3"]

    def test_convert_raw_ref_to_struct(self, memkind):
        k = memkind
        src = f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ref as k_ref

        @struct
        class Point:
            x: i32
            y: i32

        def make_ref() -> k_ref[Point]:
            p = k_alloc[Point](1)
            return p[0]

        def get_Point(x: i32, y: i32) -> Point:
            r = make_ref()
            r.x = x
            r.y = y
            p: Point = r  # convert k_ref[Point] to Point
            return p
        """
        mod = self.compile(src)
        assert mod.get_Point(1, 2) == (1, 2)

    def test_array_of_struct_getref(self, memkind):
        k = memkind
        mod = self.compile(f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr

        @struct
        class Point:
            x: i32
            y: i32

        def foo() -> k_ptr[Point]:
            arr = k_alloc[Point](2)
            arr[0].x = 1
            arr[0].y = 2
            arr[1].x = 3
            arr[1].y = 4
            return arr
        """)
        p = mod.foo()
        addr = p.addr
        self.vm.ll.mem.read_i32(p.addr) == 1
        self.vm.ll.mem.read_i32(p.addr + 4) == 2
        self.vm.ll.mem.read_i32(p.addr + 8) == 3
        self.vm.ll.mem.read_i32(p.addr + 12) == 4

    def test_array_of_struct_read_write_byval(self, memkind):
        k = memkind
        mod = self.compile(f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr

        @struct
        class Point:
            x: i32
            y: i32

        @struct
        class Rect:
            a: Point
            b: Point

        def write_point() -> k_ptr[Point]:
            arr = k_alloc[Point](2)
            arr[0] = Point(1, 2)
            arr[1] = Point(3, 4)
            return arr

        def write_rect() -> k_ptr[Rect]:
            arr = k_alloc[Rect](1)
            arr[0] = Rect(Point(5, 6), Point(7, 8))
            return arr

        def read_point() -> Point:
            arr = write_rect()
            return arr[0].b
        """)
        ptr_p = mod.write_point()
        self.vm.ll.mem.read_i32(ptr_p.addr) == 1
        self.vm.ll.mem.read_i32(ptr_p.addr + 4) == 2
        self.vm.ll.mem.read_i32(ptr_p.addr + 8) == 3
        self.vm.ll.mem.read_i32(ptr_p.addr + 12) == 4

        ptr_r = mod.write_rect()
        self.vm.ll.mem.read_i32(ptr_r.addr) == 5
        self.vm.ll.mem.read_i32(ptr_r.addr + 4) == 6
        self.vm.ll.mem.read_i32(ptr_r.addr + 8) == 7
        self.vm.ll.mem.read_i32(ptr_r.addr + 12) == 8

        p = mod.read_point()
        assert p == (7, 8)

    def test_return_struct_with_ptr(self, memkind):
        k = memkind
        mod = self.compile(f"""
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr

        @struct
        class Point:
            x: i32
            y: i32

        @struct
        class Wrapper:
            p: k_ptr[Point]

        def foo() -> Wrapper:
            p = k_alloc[Point](1)
            p.x = 1
            p.y = 2
            return Wrapper(p)
        """)
        w = mod.foo()
        addr = w.p.addr
        self.vm.ll.mem.read_i32(addr) == 1
        self.vm.ll.mem.read_i32(addr + 4) == 2
