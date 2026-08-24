from spy.tests.support import CompilerTest


class TestStructByPtr(CompilerTest):
    """
    Read/write struct fields through `gc_ptr[Struct]` for every primitive
    dtype, plus a whole-struct-by-value read.

    On the interpreter, `p.v` lowers to ptr.getfield/ptr.setfield, which call
    generic_mem_read/generic_mem_write for by-value primitive fields. The same
    dtype gap as test_ptr_mem.TestPtrMemDtypes applies: i8, u32, i64, u64, f32
    WIP on interp/doppler and pass on the C backends.

    See https://github.com/spylang/spy/issues/653 (PR0).
    """

    def test_ptr_struct_fields_all_dtypes(self):
        mod = self.compile("""
            from unsafe import gc_alloc, gc_ptr

            @struct
            class BoxI8:
                v: i8
            @struct
            class BoxU8:
                v: u8
            @struct
            class BoxI32:
                v: i32
            @struct
            class BoxU32:
                v: u32
            @struct
            class BoxI64:
                v: i64
            @struct
            class BoxU64:
                v: u64
            @struct
            class BoxF32:
                v: f32
            @struct
            class BoxF64:
                v: f64

            def f_i8(v: i32) -> i8:
                p: gc_ptr[BoxI8] = gc_alloc[BoxI8](1)
                p.v = i8(v)
                return p.v

            def f_u8(v: i32) -> u8:
                p: gc_ptr[BoxU8] = gc_alloc[BoxU8](1)
                p.v = u8(v)
                return p.v

            def f_i32(v: i32) -> i32:
                p: gc_ptr[BoxI32] = gc_alloc[BoxI32](1)
                p.v = v
                return p.v

            def f_u32(v: u32) -> u32:
                p: gc_ptr[BoxU32] = gc_alloc[BoxU32](1)
                p.v = v
                return p.v

            def f_i64(v: i32) -> i64:
                p: gc_ptr[BoxI64] = gc_alloc[BoxI64](1)
                p.v = i64(v)
                return p.v

            def f_u64(v: i32) -> u64:
                p: gc_ptr[BoxU64] = gc_alloc[BoxU64](1)
                p.v = u64(i64(v))
                return p.v

            def f_f32(v: i32) -> f32:
                p: gc_ptr[BoxF32] = gc_alloc[BoxF32](1)
                p.v = f32(v)
                return p.v

            def f_f64(v: f64) -> f64:
                p: gc_ptr[BoxF64] = gc_alloc[BoxF64](1)
                p.v = v
                return p.v

            # whole-struct-by-value read: p[0] returns a ref[B_f32] (byref for
            # struct items); assigning it to a B_f32 value derefs through
            # generic_mem_read(B_f32), which recurses field-by-field and hits
            # the same f32 gap.
            def f_struct_byval_f32(v: i32) -> f32:
                p: gc_ptr[BoxF32] = gc_alloc[BoxF32](1)
                p.v = f32(v)
                x: BoxF32 = p[0]
                return x.v
            """)
        # controls
        assert mod.f_i32(42) == 42
        assert mod.f_u8(200) == 200
        assert mod.f_f64(1.5) == 1.5
        # the gap
        assert mod.f_i8(-5) == -5
        assert mod.f_u32(42) == 42
        assert mod.f_i64(42) == 42
        assert mod.f_u64(42) == 42
        assert mod.f_f32(7) == 7.0
        assert mod.f_struct_byval_f32(7) == 7.0
