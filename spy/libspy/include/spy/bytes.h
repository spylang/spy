#ifndef SPY_BYTES_H
#define SPY_BYTES_H

#include "spy.h"
#include "spy/unsafe.h"
#include <stddef.h>

/* === Bytes layout ===

   spy_BytesObject contains length, hash and a ptr to the raw byte data.

   spy_bytes_alloc allocates spy_BytesObject AND the data buffer in a single
   allocation. The layout mirrors spy_StrObject exactly, minus the UTF-8
   invariant.
*/

typedef struct {
    size_t length;
    int32_t hash;
    spy_gc_ptr_u8 data;
} spy_BytesObject;

#define spy_BytesObject_DATA(b) ((b)->data.p)

/* gc_ptr[_bytes::BytesObject] is predeclared here, see also
   cstructwriter.py:emit_PtrType. Make sure that they stay in sync. */
typedef struct spy_unsafe$gc_ptr___bytes$BytesObject {
    spy_BytesObject *p;
#ifdef SPY_DEBUG
    ptrdiff_t length;
#endif
} spy_unsafe$gc_ptr___bytes$BytesObject;

SPY_PTR_FUNCTIONS(gc, spy_unsafe$gc_ptr___bytes$BytesObject, spy_BytesObject)
#define spy_unsafe$gc_ptr___bytes$BytesObject$NULL                                     \
    ((spy_unsafe$gc_ptr___bytes$BytesObject){0})

// short alias for manual use
typedef spy_unsafe$gc_ptr___bytes$BytesObject spy_gc_ptr_BytesObject;

static inline spy_gc_ptr_BytesObject
spy_unsafe$_bytes_to_BytesObject$impl(spy_BytesObject *b) {
    return spy_unsafe$gc_ptr___bytes$BytesObject_from_addr(b);
}

static inline spy_BytesObject *
spy_unsafe$_BytesObject_to_bytes$impl(spy_gc_ptr_BytesObject p) {
    return p.p;
}

// Layout info exported for bytes.py.
typedef struct {
    size_t size;
    size_t length_offset;
    size_t hash_offset;
    size_t data_offset;
} _spy_BytesObject_Layout;

_spy_BytesObject_Layout WASM_EXPORT(_spy_BytesObject_layout)(void);

spy_BytesObject *WASM_EXPORT(spy_bytes_alloc)(size_t length);

static inline spy_gc_ptr_BytesObject
spy_unsafe$_alloc_BytesObject$impl(int32_t length) {
    return spy_unsafe$gc_ptr___bytes$BytesObject_from_addr(
        spy_bytes_alloc((size_t)length)
    );
}

spy_BytesObject *WASM_EXPORT(spy_bytes_add)(spy_BytesObject *a, spy_BytesObject *b);

spy_BytesObject *WASM_EXPORT(spy_bytes_mul)(spy_BytesObject *a, int32_t b);

bool WASM_EXPORT(spy_bytes_eq)(spy_BytesObject *a, spy_BytesObject *b);

static inline bool
spy_bytes_ne(spy_BytesObject *a, spy_BytesObject *b) {
    return !spy_bytes_eq(a, b);
}

uint8_t WASM_EXPORT(spy_bytes_getitem)(spy_BytesObject *b, int32_t i);

int32_t WASM_EXPORT(spy_bytes_len)(spy_BytesObject *b);

spy_StrObject *WASM_EXPORT(spy_bytes_repr)(spy_BytesObject *b);

int32_t WASM_EXPORT(spy_bytes_hash)(spy_BytesObject *b);

#define spy_operator$bytes_add spy_bytes_add
#define spy_operator$bytes_mul spy_bytes_mul
#define spy_operator$bytes_eq spy_bytes_eq
#define spy_operator$bytes_ne spy_bytes_ne
#define spy_builtins$bytes$__getitem__ spy_bytes_getitem
#define spy_builtins$bytes$__len__ spy_bytes_len
#define spy_builtins$bytes$__repr__ spy_bytes_repr
#define spy_builtins$hash_bytes spy_bytes_hash

// __str__ of bytes returns its __repr__ result (matches CPython)
static inline spy_StrObject *
spy_bytes_str(spy_BytesObject *b) {
    return spy_bytes_repr(b);
}
#define spy_builtins$bytes$__str__ spy_bytes_str

#endif /* SPY_BYTES_H */
