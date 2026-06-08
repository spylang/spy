import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest, expect_errors


@pytest.fixture(params=["raw", "gc"])
def memkind(request):
    return request.param


class TestMem(CompilerTest):
    def test_memcpy(self, memkind):
        k = memkind
        src = """
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, memcpy

        def foo() -> i32:
            src: k_ptr[u8] = k_alloc[u8](4)
            dst: k_ptr[u8] = k_alloc[u8](4)
            src[0] = 10
            src[1] = 20
            src[2] = 30
            src[3] = 40
            memcpy(dst, src, 4)
            return dst[0] + dst[1] + dst[2] + dst[3]
        """.format(k=k)
        mod = self.compile(src)
        assert mod.foo() == 100

    def test_memcpy_mixed_memkind(self):
        src = """
        from unsafe import raw_alloc, raw_ptr, gc_alloc, gc_ptr, memcpy

        def foo() -> i32:
            src: raw_ptr[u8] = raw_alloc[u8](3)
            dst: gc_ptr[u8] = gc_alloc[u8](3)
            src[0] = 1
            src[1] = 2
            src[2] = 3
            memcpy(dst, src, 3)
            return dst[0] + dst[1] + dst[2]
        """
        mod = self.compile(src)
        assert mod.foo() == 6

    def test_memcpy_wrong_itemtype(self):
        src = """
        from unsafe import raw_alloc, raw_ptr, memcpy

        def foo() -> i32:
            buf: raw_ptr[i32] = raw_alloc[i32](4)
            memcpy(buf, buf, 4)
            return 0
        """
        errors = expect_errors(
            "mismatched types",
            ("expected ptr[u8], got `unsafe::raw_ptr[i32]`", "buf"),
        )
        self.compile_raises(src, "foo", errors)

    def test_memcpy_out_of_bounds(self, memkind):
        k = memkind
        src = """
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, memcpy

        def foo() -> i32:
            src: k_ptr[u8] = k_alloc[u8](4)
            dst: k_ptr[u8] = k_alloc[u8](4)
            memcpy(dst, src, 10)
            return 0
        """.format(k=k)
        mod = self.compile(src)
        with SPyError.raises("W_PanicError", match="out of bounds"):
            mod.foo()

    def test_memmove(self, memkind):
        k = memkind
        src = """
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, memmove

        def foo() -> i32:
            src: k_ptr[u8] = k_alloc[u8](4)
            dst: k_ptr[u8] = k_alloc[u8](4)
            src[0] = 10
            src[1] = 20
            src[2] = 30
            src[3] = 40
            memmove(dst, src, 4)
            return dst[0] + dst[1] + dst[2] + dst[3]
        """.format(k=k)
        mod = self.compile(src)
        assert mod.foo() == 100

    def test_memmove_wrong_itemtype(self):
        src = """
        from unsafe import raw_alloc, raw_ptr, memmove

        def foo() -> i32:
            buf: raw_ptr[i32] = raw_alloc[i32](4)
            memmove(buf, buf, 4)
            return 0
        """
        errors = expect_errors(
            "mismatched types",
            ("expected ptr[u8], got `unsafe::raw_ptr[i32]`", "buf"),
        )
        self.compile_raises(src, "foo", errors)

    def test_memmove_out_of_bounds(self, memkind):
        k = memkind
        src = """
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, memmove

        def foo() -> i32:
            src: k_ptr[u8] = k_alloc[u8](4)
            dst: k_ptr[u8] = k_alloc[u8](4)
            memmove(dst, src, 10)
            return 0
        """.format(k=k)
        mod = self.compile(src)
        with SPyError.raises("W_PanicError", match="out of bounds"):
            mod.foo()

    def test_memset(self, memkind):
        k = memkind
        src = """
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, memset

        def foo() -> i32:
            buf: k_ptr[u8] = k_alloc[u8](4)
            memset(buf, 7, 4)
            return buf[0] + buf[1] + buf[2] + buf[3]
        """.format(k=k)
        mod = self.compile(src)
        assert mod.foo() == 28

    def test_memset_wrong_itemtype(self):
        src = """
        from unsafe import raw_alloc, raw_ptr, memset

        def foo() -> i32:
            buf: raw_ptr[i32] = raw_alloc[i32](4)
            memset(buf, 0, 4)
            return 0
        """
        errors = expect_errors(
            "mismatched types",
            ("expected ptr[u8], got `unsafe::raw_ptr[i32]`", "buf"),
        )
        self.compile_raises(src, "foo", errors)

    def test_memset_out_of_bounds(self, memkind):
        k = memkind
        src = """
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, memset

        def foo() -> i32:
            buf: k_ptr[u8] = k_alloc[u8](4)
            memset(buf, 0, 10)
            return 0
        """.format(k=k)
        mod = self.compile(src)
        with SPyError.raises("W_PanicError", match="out of bounds"):
            mod.foo()

    def test_memcmp(self, memkind):
        k = memkind
        src = """
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, memset, memcmp

        def foo() -> i32:
            a: k_ptr[u8] = k_alloc[u8](4)
            b: k_ptr[u8] = k_alloc[u8](4)
            memset(a, 42, 4)
            memset(b, 42, 4)
            return memcmp(a, b, 4)

        def bar() -> i32:
            a: k_ptr[u8] = k_alloc[u8](4)
            b: k_ptr[u8] = k_alloc[u8](4)
            memset(a, 1, 4)
            memset(b, 2, 4)
            r: i32 = memcmp(a, b, 4)
            if r < 0:
                return -1
            return 1
        """.format(k=k)
        mod = self.compile(src)
        assert mod.foo() == 0
        assert mod.bar() == -1

    def test_memcmp_wrong_itemtype(self):
        src = """
        from unsafe import raw_alloc, raw_ptr, memcmp

        def foo() -> i32:
            buf: raw_ptr[i32] = raw_alloc[i32](4)
            return memcmp(buf, buf, 4)
        """
        errors = expect_errors(
            "mismatched types",
            ("expected ptr[u8], got `unsafe::raw_ptr[i32]`", "buf"),
        )
        self.compile_raises(src, "foo", errors)

    def test_memcmp_out_of_bounds(self, memkind):
        k = memkind
        src = """
        from unsafe import {k}_alloc as k_alloc, {k}_ptr as k_ptr, memcmp

        def foo() -> i32:
            a: k_ptr[u8] = k_alloc[u8](4)
            b: k_ptr[u8] = k_alloc[u8](4)
            return memcmp(a, b, 10)
        """.format(k=k)
        mod = self.compile(src)
        with SPyError.raises("W_PanicError", match="out of bounds"):
            mod.foo()
