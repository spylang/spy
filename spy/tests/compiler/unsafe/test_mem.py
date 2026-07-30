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
        from unsafe import (
            {k}_alloc as k_alloc, {k}_ptr as k_ptr,
            ptr_copy, ptr_copy_slice,
        )

        def fn_ptr() -> i32:
            src: k_ptr[u8] = k_alloc[u8](4)
            dst: k_ptr[u8] = k_alloc[u8](4)
            src[0] = 10
            src[1] = 20
            src[2] = 30
            src[3] = 40
            ptr_copy(dst, src, 4)
            return dst[0] + dst[1] + dst[2] + dst[3]

        def fn_slice() -> i32:
            src: k_ptr[u8] = k_alloc[u8](4)
            dst: k_ptr[u8] = k_alloc[u8](4)
            src[0] = 10
            src[1] = 20
            src[2] = 30
            src[3] = 40
            dst[0] = 0
            dst[1] = 0
            dst[2] = 0
            dst[3] = 0
            # copy src[1:3] into dst[2:4]
            ptr_copy_slice(dst, 2, 4, src, 1, 3)
            return i32(dst[0])*1000 + i32(dst[1])*100 + i32(dst[2])*10 + i32(dst[3])
        """.format(k=k)
        mod = self.compile(src)
        assert mod.fn_ptr() == 100
        assert mod.fn_slice() == 200 + 30  # dst[2]=20, dst[3]=30; rest=0

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
        from unsafe import (
            {k}_alloc as k_alloc, {k}_ptr as k_ptr,
            ptr_copy, ptr_copy_slice,
        )

        def fn_ptr() -> i32:
            src: k_ptr[i32] = k_alloc[i32](4)
            dst: k_ptr[i32] = k_alloc[i32](4)
            src[0] = 100
            src[1] = 200
            src[2] = 300
            src[3] = 400
            ptr_copy(dst, src, 4)
            return dst[0] + dst[1] + dst[2] + dst[3]

        def fn_slice() -> i32:
            src: k_ptr[i32] = k_alloc[i32](4)
            dst: k_ptr[i32] = k_alloc[i32](4)
            src[0] = 100
            src[1] = 200
            src[2] = 300
            src[3] = 400
            dst[0] = 0
            dst[1] = 0
            dst[2] = 0
            dst[3] = 0
            ptr_copy_slice(dst, 2, 4, src, 1, 3)
            return dst[0] + dst[1] + dst[2] + dst[3]
        """.format(k=k)
        mod = self.compile(src)
        assert mod.fn_ptr() == 1000
        assert mod.fn_slice() == 500  # dst[2]=200, dst[3]=300

    def test_ptr_copy_out_of_bounds(self, memkind):
        k = memkind
        src = """
        from unsafe import (
            {k}_alloc as k_alloc, {k}_ptr as k_ptr,
            ptr_copy, ptr_copy_slice,
        )

        def fn_ptr() -> i32:
            src: k_ptr[i32] = k_alloc[i32](4)
            dst: k_ptr[i32] = k_alloc[i32](4)
            ptr_copy(dst, src, 10)
            return 0

        def fn_slice() -> i32:
            src: k_ptr[i32] = k_alloc[i32](4)
            dst: k_ptr[i32] = k_alloc[i32](4)
            ptr_copy_slice(dst, 0, 10, src, 0, 10)
            return 0

        def fn_slice_mismatch() -> i32:
            src: k_ptr[i32] = k_alloc[i32](4)
            dst: k_ptr[i32] = k_alloc[i32](4)
            ptr_copy_slice(dst, 0, 3, src, 0, 2)
            return 0
        """.format(k=k)
        mod = self.compile(src)
        with SPyError.raises("W_PanicError", match="out of bounds"):
            mod.fn_ptr()
        with SPyError.raises("W_PanicError", match="out of bounds"):
            mod.fn_slice()
        with SPyError.raises("W_PanicError", match="length mismatch"):
            mod.fn_slice_mismatch()

    def test_ptr_copy_overlap(self, memkind):
        k = memkind
        src = """
        from unsafe import (
            {k}_alloc as k_alloc, {k}_ptr as k_ptr,
            ptr_copy, ptr_copy_slice,
        )

        def fn_ptr() -> i32:
            buf: k_ptr[u8] = k_alloc[u8](4)
            ptr_copy(buf, buf, 4)
            return 0

        def fn_slice() -> i32:
            buf: k_ptr[u8] = k_alloc[u8](4)
            ptr_copy_slice(buf, 0, 3, buf, 1, 4)
            return 0
        """.format(k=k)
        mod = self.compile(src)
        with SPyError.raises("W_PanicError", match="ptr_copy regions overlap"):
            mod.fn_ptr()
        with SPyError.raises("W_PanicError", match="ptr_copy_slice regions overlap"):
            mod.fn_slice()

    def test_ptr_move(self, memkind):
        k = memkind
        src = """
        from unsafe import (
            {k}_alloc as k_alloc, {k}_ptr as k_ptr,
            ptr_move, ptr_move_slice,
        )

        def fn_ptr() -> i32:
            src: k_ptr[u8] = k_alloc[u8](4)
            dst: k_ptr[u8] = k_alloc[u8](4)
            src[0] = 10
            src[1] = 20
            src[2] = 30
            src[3] = 40
            ptr_move(dst, src, 4)
            return dst[0] + dst[1] + dst[2] + dst[3]

        def fn_slice() -> i32:
            src: k_ptr[u8] = k_alloc[u8](4)
            dst: k_ptr[u8] = k_alloc[u8](4)
            src[0] = 10
            src[1] = 20
            src[2] = 30
            src[3] = 40
            dst[0] = 0
            dst[1] = 0
            dst[2] = 0
            dst[3] = 0
            ptr_move_slice(dst, 2, 4, src, 1, 3)
            return i32(dst[0])*1000 + i32(dst[1])*100 + i32(dst[2])*10 + i32(dst[3])
        """.format(k=k)
        mod = self.compile(src)
        assert mod.fn_ptr() == 100
        assert mod.fn_slice() == 200 + 30

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
        from unsafe import (
            {k}_alloc as k_alloc, {k}_ptr as k_ptr,
            ptr_move, ptr_move_slice,
        )

        def fn_ptr() -> i32:
            src: k_ptr[u8] = k_alloc[u8](4)
            dst: k_ptr[u8] = k_alloc[u8](4)
            ptr_move(dst, src, 10)
            return 0

        def fn_slice() -> i32:
            src: k_ptr[u8] = k_alloc[u8](4)
            dst: k_ptr[u8] = k_alloc[u8](4)
            ptr_move_slice(dst, 0, 10, src, 0, 10)
            return 0

        def fn_slice_mismatch() -> i32:
            src: k_ptr[u8] = k_alloc[u8](4)
            dst: k_ptr[u8] = k_alloc[u8](4)
            ptr_move_slice(dst, 0, 3, src, 0, 2)
            return 0
        """.format(k=k)
        mod = self.compile(src)
        with SPyError.raises("W_PanicError", match="out of bounds"):
            mod.fn_ptr()
        with SPyError.raises("W_PanicError", match="out of bounds"):
            mod.fn_slice()
        with SPyError.raises("W_PanicError", match="length mismatch"):
            mod.fn_slice_mismatch()

    def test_ptr_setbytes(self, memkind):
        k = memkind
        src = """
        from unsafe import (
            {k}_alloc as k_alloc, {k}_ptr as k_ptr,
            ptr_setbytes, ptr_setbytes_slice,
        )

        def fn_ptr() -> i32:
            buf: k_ptr[u8] = k_alloc[u8](4)
            ptr_setbytes(buf, 7, 4)
            return buf[0] + buf[1] + buf[2] + buf[3]

        def fn_slice() -> i32:
            buf: k_ptr[u8] = k_alloc[u8](4)
            buf[0] = 0
            buf[1] = 0
            buf[2] = 0
            buf[3] = 0
            ptr_setbytes_slice(buf, 1, 3, 7)
            return i32(buf[0])*1000 + i32(buf[1])*100 + i32(buf[2])*10 + i32(buf[3])
        """.format(k=k)
        mod = self.compile(src)
        assert mod.fn_ptr() == 28
        assert mod.fn_slice() == 700 + 70

    def test_ptr_setbytes_not_a_ptr(self):
        src = """
        from unsafe import ptr_setbytes

        def foo() -> i32:
            x: i32 = 0
            ptr_setbytes(x, 0, 4)
            return 0
        """
        errors = expect_errors(
            "mismatched types",
            ("expected ptr[T], got `i32`", "x"),
        )
        self.compile_raises(src, "foo", errors)

    def test_ptr_setbytes_out_of_bounds(self, memkind):
        k = memkind
        src = """
        from unsafe import (
            {k}_alloc as k_alloc, {k}_ptr as k_ptr,
            ptr_setbytes, ptr_setbytes_slice,
        )

        def fn_ptr() -> i32:
            buf: k_ptr[u8] = k_alloc[u8](4)
            ptr_setbytes(buf, 0, 10)
            return 0

        def fn_slice() -> i32:
            buf: k_ptr[u8] = k_alloc[u8](4)
            ptr_setbytes_slice(buf, 0, 10, 0)
            return 0
        """.format(k=k)
        mod = self.compile(src)
        with SPyError.raises("W_PanicError", match="out of bounds"):
            mod.fn_ptr()
        with SPyError.raises("W_PanicError", match="out of bounds"):
            mod.fn_slice()

    def test_ptr_cmp(self, memkind):
        k = memkind
        src = """
        from unsafe import (
            {k}_alloc as k_alloc, {k}_ptr as k_ptr,
            ptr_setbytes, ptr_cmp, ptr_cmp_slice,
        )

        def fn_ptr_eq() -> i32:
            a: k_ptr[u8] = k_alloc[u8](4)
            b: k_ptr[u8] = k_alloc[u8](4)
            ptr_setbytes(a, 42, 4)
            ptr_setbytes(b, 42, 4)
            return ptr_cmp(a, b, 4)

        def fn_ptr_lt() -> i32:
            a: k_ptr[u8] = k_alloc[u8](4)
            b: k_ptr[u8] = k_alloc[u8](4)
            ptr_setbytes(a, 1, 4)
            ptr_setbytes(b, 2, 4)
            r: i32 = ptr_cmp(a, b, 4)
            if r < 0:
                return -1
            return 1

        def fn_slice_eq() -> i32:
            a: k_ptr[u8] = k_alloc[u8](4)
            b: k_ptr[u8] = k_alloc[u8](4)
            a[0] = 1
            a[1] = 7
            a[2] = 7
            a[3] = 9
            b[0] = 2
            b[1] = 7
            b[2] = 7
            b[3] = 8
            return ptr_cmp_slice(a, 1, 3, b, 1, 3)

        def fn_slice_lt() -> i32:
            a: k_ptr[u8] = k_alloc[u8](4)
            b: k_ptr[u8] = k_alloc[u8](4)
            ptr_setbytes(a, 1, 4)
            ptr_setbytes(b, 2, 4)
            r: i32 = ptr_cmp_slice(a, 0, 2, b, 0, 2)
            if r < 0:
                return -1
            return 1
        """.format(k=k)
        mod = self.compile(src)
        assert mod.fn_ptr_eq() == 0
        assert mod.fn_ptr_lt() == -1
        assert mod.fn_slice_eq() == 0
        assert mod.fn_slice_lt() == -1

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
        from unsafe import (
            {k}_alloc as k_alloc, {k}_ptr as k_ptr,
            ptr_cmp, ptr_cmp_slice,
        )

        def fn_ptr() -> i32:
            a: k_ptr[u8] = k_alloc[u8](4)
            b: k_ptr[u8] = k_alloc[u8](4)
            return ptr_cmp(a, b, 10)

        def fn_slice() -> i32:
            a: k_ptr[u8] = k_alloc[u8](4)
            b: k_ptr[u8] = k_alloc[u8](4)
            return ptr_cmp_slice(a, 0, 10, b, 0, 10)

        def fn_slice_mismatch() -> i32:
            a: k_ptr[u8] = k_alloc[u8](4)
            b: k_ptr[u8] = k_alloc[u8](4)
            return ptr_cmp_slice(a, 0, 3, b, 0, 2)
        """.format(k=k)
        mod = self.compile(src)
        with SPyError.raises("W_PanicError", match="out of bounds"):
            mod.fn_ptr()
        with SPyError.raises("W_PanicError", match="out of bounds"):
            mod.fn_slice()
        with SPyError.raises("W_PanicError", match="length mismatch"):
            mod.fn_slice_mismatch()

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

    def test_memcpy_i32_rejected(self):
        src = """
        from unsafe import raw_alloc, raw_ptr, memcpy

        def foo() -> i32:
            buf: raw_ptr[i32] = raw_alloc[i32](4)
            memcpy(buf, buf, 4)
            return 0
        """
        errors = expect_errors(
            "mismatched types",
            ("expected ptr[u8] or ptr[i8], got `unsafe::raw_ptr[i32]`", "buf"),
            ("help: use `ptr_copy` instead", "buf"),
        )
        self.compile_raises(src, "foo", errors)

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

    def test_memmove_i32_rejected(self):
        src = """
        from unsafe import raw_alloc, raw_ptr, memmove

        def foo() -> i32:
            buf: raw_ptr[i32] = raw_alloc[i32](4)
            memmove(buf, buf, 4)
            return 0
        """
        errors = expect_errors(
            "mismatched types",
            ("expected ptr[u8] or ptr[i8], got `unsafe::raw_ptr[i32]`", "buf"),
            ("help: use `ptr_move` instead", "buf"),
        )
        self.compile_raises(src, "foo", errors)

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

    def test_memset_i32_rejected(self):
        src = """
        from unsafe import raw_alloc, raw_ptr, memset

        def foo() -> i32:
            buf: raw_ptr[i32] = raw_alloc[i32](4)
            memset(buf, 0, 4)
            return 0
        """
        errors = expect_errors(
            "mismatched types",
            ("expected ptr[u8] or ptr[i8], got `unsafe::raw_ptr[i32]`", "buf"),
            ("help: use `ptr_setbytes` instead", "buf"),
        )
        self.compile_raises(src, "foo", errors)

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
        """.format(k=k)
        mod = self.compile(src)
        assert mod.foo() == 0

    def test_memcmp_i32_rejected(self):
        src = """
        from unsafe import raw_alloc, raw_ptr, memcmp

        def foo() -> i32:
            buf: raw_ptr[i32] = raw_alloc[i32](4)
            return memcmp(buf, buf, 4)
        """
        errors = expect_errors(
            "mismatched types",
            ("expected ptr[u8] or ptr[i8], got `unsafe::raw_ptr[i32]`", "buf"),
            ("help: use `ptr_cmp` instead", "buf"),
        )
        self.compile_raises(src, "foo", errors)
