import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest, expect_errors


@pytest.fixture(params=["raw", "gc"])
def memkind(request):
    return request.param


class TestMem(CompilerTest):
    def test_ptr_copy(self, memkind):
        k = memkind
        src = """
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, ptr_copy

        def foo() -> i32:
            src: k_ptr[u8] = k_alloc[u8](4)
            dst: k_ptr[u8] = k_alloc[u8](4)
            src[0] = 10
            src[1] = 20
            src[2] = 30
            src[3] = 40
            ptr_copy(dst, src, 4)
            return dst[0] + dst[1] + dst[2] + dst[3]
        """.format(k=k)
        mod = self.compile(src)
        assert mod.foo() == 100

    def test_ptr_copy_mixed_memkind(self):
        src = """
        from unsafe import raw_alloc, raw_ptr, gc_alloc, gc_ptr, ptr_copy

        def foo() -> i32:
            src: raw_ptr[u8] = raw_alloc[u8](3)
            dst: gc_ptr[u8] = gc_alloc[u8](3)
            src[0] = 1
            src[1] = 2
            src[2] = 3
            ptr_copy(dst, src, 3)
            return dst[0] + dst[1] + dst[2]
        """
        mod = self.compile(src)
        assert mod.foo() == 6

    def test_ptr_copy_not_a_ptr(self):
        src = """
        from unsafe import ptr_copy

        def foo() -> i32:
            x: i32 = 0
            ptr_copy(x, x, 4)
            return 0
        """
        errors = expect_errors(
            "mismatched types",
            ("expected ptr[T], got `i32`", "x"),
        )
        self.compile_raises(src, "foo", errors)

    def test_ptr_copy_incompatible_ptrs(self):
        src = """
        from unsafe import raw_alloc, raw_ptr, ptr_copy

        def foo() -> i32:
            a: raw_ptr[i32] = raw_alloc[i32](4)
            b: raw_ptr[u8] = raw_alloc[u8](4)
            ptr_copy(a, b, 4)
            return 0
        """
        errors = expect_errors(
            "mismatched types",
            ("`unsafe::raw_ptr[i32]`", "a"),
            ("`unsafe::raw_ptr[u8]`", "b"),
        )
        self.compile_raises(src, "foo", errors)

    def test_ptr_copy_i32(self, memkind):
        k = memkind
        src = """
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, ptr_copy

        def foo() -> i32:
            src: k_ptr[i32] = k_alloc[i32](4)
            dst: k_ptr[i32] = k_alloc[i32](4)
            src[0] = 100
            src[1] = 200
            src[2] = 300
            src[3] = 400
            ptr_copy(dst, src, 4)
            return dst[0] + dst[1] + dst[2] + dst[3]
        """.format(k=k)
        mod = self.compile(src)
        assert mod.foo() == 1000

    def test_ptr_copy_i32_out_of_bounds(self, memkind):
        k = memkind
        src = """
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, ptr_copy

        def foo() -> i32:
            src: k_ptr[i32] = k_alloc[i32](4)
            dst: k_ptr[i32] = k_alloc[i32](4)
            ptr_copy(dst, src, 10)
            return 0
        """.format(k=k)
        mod = self.compile(src)
        with SPyError.raises("W_PanicError", match="out of bounds"):
            mod.foo()

    def test_ptr_copy_out_of_bounds(self, memkind):
        k = memkind
        src = """
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, ptr_copy

        def foo() -> i32:
            src: k_ptr[u8] = k_alloc[u8](4)
            dst: k_ptr[u8] = k_alloc[u8](4)
            ptr_copy(dst, src, 10)
            return 0
        """.format(k=k)
        mod = self.compile(src)
        with SPyError.raises("W_PanicError", match="out of bounds"):
            mod.foo()

    def test_ptr_move(self, memkind):
        k = memkind
        src = """
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, ptr_move

        def foo() -> i32:
            src: k_ptr[u8] = k_alloc[u8](4)
            dst: k_ptr[u8] = k_alloc[u8](4)
            src[0] = 10
            src[1] = 20
            src[2] = 30
            src[3] = 40
            ptr_move(dst, src, 4)
            return dst[0] + dst[1] + dst[2] + dst[3]
        """.format(k=k)
        mod = self.compile(src)
        assert mod.foo() == 100

    def test_ptr_move_not_a_ptr(self):
        src = """
        from unsafe import ptr_move

        def foo() -> i32:
            x: i32 = 0
            ptr_move(x, x, 4)
            return 0
        """
        errors = expect_errors(
            "mismatched types",
            ("expected ptr[T], got `i32`", "x"),
        )
        self.compile_raises(src, "foo", errors)

    def test_ptr_move_incompatible_ptrs(self):
        src = """
        from unsafe import raw_alloc, raw_ptr, ptr_move

        def foo() -> i32:
            a: raw_ptr[i32] = raw_alloc[i32](4)
            b: raw_ptr[u8] = raw_alloc[u8](4)
            ptr_move(a, b, 4)
            return 0
        """
        errors = expect_errors(
            "mismatched types",
            ("`unsafe::raw_ptr[i32]`", "a"),
            ("`unsafe::raw_ptr[u8]`", "b"),
        )
        self.compile_raises(src, "foo", errors)

    def test_ptr_move_out_of_bounds(self, memkind):
        k = memkind
        src = """
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, ptr_move

        def foo() -> i32:
            src: k_ptr[u8] = k_alloc[u8](4)
            dst: k_ptr[u8] = k_alloc[u8](4)
            ptr_move(dst, src, 10)
            return 0
        """.format(k=k)
        mod = self.compile(src)
        with SPyError.raises("W_PanicError", match="out of bounds"):
            mod.foo()

    def test_ptr_set(self, memkind):
        k = memkind
        src = """
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, ptr_set

        def foo() -> i32:
            buf: k_ptr[u8] = k_alloc[u8](4)
            ptr_set(buf, 7, 4)
            return buf[0] + buf[1] + buf[2] + buf[3]
        """.format(k=k)
        mod = self.compile(src)
        assert mod.foo() == 28

    def test_ptr_set_not_a_ptr(self):
        src = """
        from unsafe import ptr_set

        def foo() -> i32:
            x: i32 = 0
            ptr_set(x, 0, 4)
            return 0
        """
        errors = expect_errors(
            "mismatched types",
            ("expected ptr[T], got `i32`", "x"),
        )
        self.compile_raises(src, "foo", errors)

    def test_ptr_set_out_of_bounds(self, memkind):
        k = memkind
        src = """
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, ptr_set

        def foo() -> i32:
            buf: k_ptr[u8] = k_alloc[u8](4)
            ptr_set(buf, 0, 10)
            return 0
        """.format(k=k)
        mod = self.compile(src)
        with SPyError.raises("W_PanicError", match="out of bounds"):
            mod.foo()

    def test_ptr_cmp(self, memkind):
        k = memkind
        src = """
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, ptr_set, ptr_cmp

        def foo() -> i32:
            a: k_ptr[u8] = k_alloc[u8](4)
            b: k_ptr[u8] = k_alloc[u8](4)
            ptr_set(a, 42, 4)
            ptr_set(b, 42, 4)
            return ptr_cmp(a, b, 4)

        def bar() -> i32:
            a: k_ptr[u8] = k_alloc[u8](4)
            b: k_ptr[u8] = k_alloc[u8](4)
            ptr_set(a, 1, 4)
            ptr_set(b, 2, 4)
            r: i32 = ptr_cmp(a, b, 4)
            if r < 0:
                return -1
            return 1
        """.format(k=k)
        mod = self.compile(src)
        assert mod.foo() == 0
        assert mod.bar() == -1

    def test_ptr_cmp_not_a_ptr(self):
        src = """
        from unsafe import ptr_cmp

        def foo() -> i32:
            x: i32 = 0
            return ptr_cmp(x, x, 4)
        """
        errors = expect_errors(
            "mismatched types",
            ("expected ptr[T], got `i32`", "x"),
        )
        self.compile_raises(src, "foo", errors)

    def test_ptr_cmp_incompatible_ptrs(self):
        src = """
        from unsafe import raw_alloc, raw_ptr, ptr_cmp

        def foo() -> i32:
            a: raw_ptr[i32] = raw_alloc[i32](4)
            b: raw_ptr[u8] = raw_alloc[u8](4)
            return ptr_cmp(a, b, 4)
        """
        errors = expect_errors(
            "mismatched types",
            ("`unsafe::raw_ptr[i32]`", "a"),
            ("`unsafe::raw_ptr[u8]`", "b"),
        )
        self.compile_raises(src, "foo", errors)

    def test_ptr_cmp_out_of_bounds(self, memkind):
        k = memkind
        src = """
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, ptr_cmp

        def foo() -> i32:
            a: k_ptr[u8] = k_alloc[u8](4)
            b: k_ptr[u8] = k_alloc[u8](4)
            return ptr_cmp(a, b, 10)
        """.format(k=k)
        mod = self.compile(src)
        with SPyError.raises("W_PanicError", match="out of bounds"):
            mod.foo()
