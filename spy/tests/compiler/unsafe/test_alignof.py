"""
`alignof` is usable from interp and app levels.
"""

import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest, no_C
from spy.vm.b import B
from spy.vm.modules.unsafe.misc import alignof


def test_alignof_primitives():
    assert alignof(B.w_bool) == 1
    assert alignof(B.w_i8) == 1
    assert alignof(B.w_u8) == 1
    assert alignof(B.w_i32) == 4
    assert alignof(B.w_u32) == 4
    assert alignof(B.w_f32) == 4
    assert alignof(B.w_i64) == 8
    assert alignof(B.w_u64) == 8
    assert alignof(B.w_f64) == 8


def test_alignof_not_implemented():
    with pytest.raises(SPyError, match="not implemented"):
        alignof(B.w_dynamic)


@no_C
class TestAlign(CompilerTest):
    def test_all_i32_fields(self):
        src = """
            @struct
            class Point:
                x: i32
                y: i32
            """
        mod = self.compile(src)
        w_Point = mod.w_mod.getattr("Point")
        assert alignof(w_Point) == 4

    def test_mixed_field_sizes(self):
        src = """
            @struct
            class Mixed:
                a: i8
                b: f64
                c: i32
            """
        mod = self.compile(src)
        w_Mixed = mod.w_mod.getattr("Mixed")
        assert alignof(w_Mixed) == 8

    def test_nested_struct(self):
        src = """
            @struct
            class Inner:
                a: i8
                b: f64

            @struct
            class Outer:
                x: i32
                inner: Inner
            """
        mod = self.compile(src)
        w_Outer = mod.w_mod.getattr("Outer")
        assert alignof(w_Outer) == 8

    def test_empty_struct(self):
        src = """
            @struct
            class Empty:
                pass
            """
        mod = self.compile(src)
        w_Empty = mod.w_mod.getattr("Empty")
        assert alignof(w_Empty) == 1

    def test_primitive_blue(self):
        src = """
            from unsafe import alignof
            from __spy__ import COLOR

            def foo() -> i32:
                N = alignof(i32)
                assert COLOR(N) == "blue"
                return N
            """
        mod = self.compile(src)
        assert mod.foo() == 4

    def test_struct(self):
        src = """
            from unsafe import alignof

            @struct
            class Mixed:
                a: i8
                b: f64
                c: i32

            def foo() -> i32:
                return alignof(Mixed)
            """
        mod = self.compile(src)
        assert mod.foo() == 8
