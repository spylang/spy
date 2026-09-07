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
    assert alignof(B.w_dynamic) == 1


@no_C
class TestAlign(CompilerTest):
    def test_all_i32_fields(self):
        mod = self.compile(
            """
            @struct
            class Point:
                x: i32
                y: i32
            """
        )
        w_Point = mod.w_mod.getattr("Point")
        assert alignof(w_Point) == 4

    def test_mixed_field_sizes(self):
        mod = self.compile(
            """
            @struct
            class Mixed:
                a: i8
                b: f64
                c: i32
            """
        )
        w_Mixed = mod.w_mod.getattr("Mixed")
        assert alignof(w_Mixed) == 8

    def test_nested_struct(self):
        mod = self.compile(
            """
            @struct
            class Inner:
                a: i8
                b: f64

            @struct
            class Outer:
                x: i32
                inner: Inner
            """
        )
        w_Outer = mod.w_mod.getattr("Outer")
        assert alignof(w_Outer) == 8

    def test_empty_struct(self):
        mod = self.compile(
            """
            @struct
            class Empty:
                pass
            """
        )
        w_Empty = mod.w_mod.getattr("Empty")
        assert alignof(w_Empty) == 1

    def test_primitive_blue(self):
        mod = self.compile(
            """
            from unsafe import alignof
            from __spy__ import COLOR

            def foo() -> i32:
                N = alignof(i32)
                assert COLOR(N) == "blue"
                return N
            """
        )
        assert mod.foo() == 4

    def test_struct(self):
        mod = self.compile(
            """
            from unsafe import alignof

            @struct
            class Mixed:
                a: i8
                b: f64
                c: i32

            def foo() -> i32:
                return alignof(Mixed)
            """
        )
        assert mod.foo() == 8
