from spy.errors import SPyError
from spy.tests.support import CompilerTest, expect_errors, only_C, only_interp
from spy.tests.wasm_wrapper import WasmPtr
from spy.vm.b import B
from spy.vm.modules.unsafe import UNSAFE
from spy.vm.modules.unsafe.ptr import W_Ptr


class TestUnsafePtr(CompilerTest):
    @only_interp
    def test_ptrtype_repr(self):
        w_ptrtype = self.vm.fast_call(UNSAFE.w_make_ptr_type, [B.w_i32])
        assert repr(w_ptrtype) == "<spy type 'unsafe::ptr[i32]'>"

    @only_interp
    def test_itemtype(self):
        mod = self.compile("""
        from unsafe import ptr

        def get_itemtype() -> type:
            return ptr[i32].itemtype
        """)
        w_T = mod.get_itemtype(unwrap=False)
        assert w_T is B.w_i32

    def test_gc_alloc(self):
        mod = self.compile("""
        from unsafe import gc_alloc, ptr

        def foo() -> i32:
            # XXX: ideally we want gc_alloc[i32](1), but we can't for now
            buf = gc_alloc(i32)(1)
            buf[0] = 42
            return buf[0]

        def bar(i: i32) -> f64:
            # make sure that we can use other item types as well
            buf = gc_alloc(f64)(3)
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
        mod = self.compile("""
        from unsafe import gc_alloc, ptr

        def foo(i: i32) -> i32:
            buf = gc_alloc(i32)(3)
            buf[0] = 0
            buf[1] = 100
            buf[2] = 200
            return buf[i]

        def bar(i: i32, v: i32) -> i32:
            buf = gc_alloc(i32)(3)
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

    def test_ptr_to_struct(self):
        mod = self.compile("""
        from unsafe import gc_alloc, ptr

        @struct
        class Point:
            x: i32
            y: f64

        def make_point(x: i32, y: f64) -> ptr[Point]:
            p = gc_alloc(Point)(1)
            p.x = x
            p.y = y
            return p

        def foo(x: i32, y: f64) -> f64:
            p = make_point(x, y)
            return p.x + p.y
        """)
        assert mod.foo(3, 4.5) == 7.5

    def test_ptr_to_string(self):
        mod = self.compile("""
        from unsafe import gc_alloc, ptr

        def make_str_ptr(s: str) -> ptr[str]:
            p = gc_alloc(str)(1)
            p[0] = s
            return p

        def foo() -> str:
            p = make_str_ptr("hello")
            return p[0]
        """)
        assert mod.foo() == "hello"

    @only_interp
    def test_dir_ptr(self):
        mod = self.compile("""
        from __spy__ import interp_list
        from unsafe import gc_alloc, ptr

        @struct
        class Point:
            x: i32
            y: i32

        def dir_ptr_point() -> interp_list[str]:
            p = gc_alloc(Point)(1)
            return dir(p)
        """)
        d = mod.dir_ptr_point()
        assert "x" in d
        assert "y" in d

    def test_struct_wrong_field(self):
        src = """
        from unsafe import ptr, gc_alloc

        @struct
        class Point:
            x: i32
            y: i32

        def foo() -> None:
            p = gc_alloc(Point)(1)
            p.z = 42
        """
        errors = expect_errors(
            "type `unsafe::ptr[test::Point]` does not support assignment to attribute 'z'",
            ("this is `unsafe::ptr[test::Point]`", "p"),
        )
        self.compile_raises(src, "foo", errors)

    def test_nested_struct(self):
        mod = self.compile("""
        from unsafe import gc_alloc, ptr

        @struct
        class Point:
            x: i32
            y: i32

        @struct
        class Rect:
            a: Point
            b: Point

        def make_rect(x0: i32, y0: i32, x1: i32, y1: i32) -> ptr[Rect]:
            r = gc_alloc(Rect)(1)

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

    def test_can_allocate_ptr(self):
        mod = self.compile("""
        from unsafe import gc_alloc, ptr

        @struct
        class Array:
            n: i32
            buf: ptr[i32]

        def foo(i: i32) -> i32:
            arr = gc_alloc(Array)(1)
            arr.n = 3
            arr.buf = gc_alloc(i32)(4)
            arr.buf[0] = 1
            arr.buf[1] = 2
            arr.buf[2] = 3
            return arr.buf[i]
        """)
        assert mod.foo(2) == 3

    def test_generic_struct(self):
        mod = self.compile("""
        from unsafe import gc_alloc, ptr

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
            p = gc_alloc(Point_i32)(1)
            p.x = 1
            p.y = 2
            return p.x + p.y

        def bar() -> f64:
            p = gc_alloc(Point_f64)(1)
            p.x = 1.2
            p.y = 3.4
            return p.x + p.y
        """)
        assert mod.foo() == 3
        assert mod.bar() == 4.6

    def test_ptr_NULL(self):
        mod = self.compile("""
        from unsafe import ptr

        def foo() -> ptr[i32]:
            return ptr[i32].NULL
        """)
        w_p = mod.foo()
        if self.backend in ("interp", "doppler"):
            assert isinstance(w_p, W_Ptr)
            assert w_p.addr == 0
            assert w_p.length == 0
            assert repr(w_p) == "W_Ptr(i32, NULL)"
        else:
            assert isinstance(w_p, WasmPtr)
            assert w_p.addr == 0
            assert w_p.length == 0

    @only_C
    def test_ptr_NULL_check(self):
        mod = self.compile("""
        from unsafe import ptr

        null_ptr: ptr[i32] = ptr[i32].NULL

        def foo(i: i32) -> i32:
            return null_ptr[i]

        def bar(i: i32, v: i32) -> None:
            null_ptr[i] = v
        """)
        with SPyError.raises("W_PanicError", "cannot dereference NULL pointer"):
            mod.foo(1)
        with SPyError.raises("W_PanicError", "cannot dereference NULL pointer"):
            mod.bar(1, 10)

    def test_NULL_in_global(self):
        mod = self.compile("""
        from unsafe import ptr

        global_ptr: ptr[i32] = ptr[i32].NULL

        def is_null() -> bool:
            return global_ptr == ptr[i32].NULL
        """)
        assert mod.is_null() is True

    def test_ptr_truth(self):
        mod = self.compile("""
        from unsafe import ptr, gc_alloc

        def is_null(p: ptr[i32]) -> bool:
            if p:
                return False
            else:
                return True

        def foo() -> bool:
            return is_null(ptr[i32].NULL)

        def bar() -> bool:
            p = gc_alloc(i32)(1)
            return is_null(p)

        """)
        assert mod.foo() is True
        assert mod.bar() is False

    def test_struct_with_ptr_to_itself(self, capfd):
        mod = self.compile("""
        from unsafe import gc_alloc, ptr

        @struct
        class Node:
            val: i32
            next: ptr[Node]

        def new_node(val: i32) -> ptr[Node]:
            n = gc_alloc(Node)(1)
            n.val = val
            n.next = ptr[Node].NULL
            return n

        def alloc_list(a: i32, b: i32, c: i32) -> ptr[Node]:
            lst = new_node(a)
            lst.next = new_node(b)
            lst.next.next = new_node(c)
            return lst

        def print_list(n: ptr[Node]) -> None:
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

    def test_array_of_struct_getref(self):
        mod = self.compile("""
        from unsafe import gc_alloc, ptr

        @struct
        class Point:
            x: i32
            y: i32

        def foo() -> ptr[Point]:
            arr = gc_alloc(Point)(2)
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

    def test_array_of_struct_read_write_byval(self):
        mod = self.compile("""
        from unsafe import gc_alloc, ptr

        @struct
        class Point:
            x: i32
            y: i32

        @struct
        class Rect:
            a: Point
            b: Point

        def write_point() -> ptr[Point]:
            arr = gc_alloc(Point)(2)
            arr[0] = Point(1, 2)
            arr[1] = Point(3, 4)
            return arr

        def write_rect() -> ptr[Rect]:
            arr = gc_alloc(Rect)(1)
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

    def test_return_struct_with_ptr(self):
        mod = self.compile("""
        from unsafe import gc_alloc, ptr

        @struct
        class Point:
            x: i32
            y: i32

        @struct
        class Wrapper:
            p: ptr[Point]

        def foo() -> Wrapper:
            p = gc_alloc(Point)(1)
            p.x = 1
            p.y = 2
            return Wrapper(p)
        """)
        w = mod.foo()
        addr = w.p.addr
        self.vm.ll.mem.read_i32(addr) == 1
        self.vm.ll.mem.read_i32(addr + 4) == 2
