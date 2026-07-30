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

/* SPY_BYTES_LITERAL(N, "content") is a struct initializer for spy_BytesObject,
   useful for static globals and for-test literals. Mirrors SPY_STR_LITERAL. */
#ifdef SPY_DEBUG
#  define SPY_BYTES_LITERAL(N, S)                                                      \
      {                                                                                \
          (N), 0, {                                                                    \
              (uint8_t *)(S), (ptrdiff_t)(N)                                           \
          }                                                                            \
      }
#else
#  define SPY_BYTES_LITERAL(N, S)                                                      \
      {                                                                                \
          (N), 0, {                                                                    \
              (uint8_t *)(S)                                                           \
          }                                                                            \
      }
#endif

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

int32_t WASM_EXPORT(spy_bytes_hash)(spy_BytesObject *b);
#define spy_builtins$bytes$__hash__ spy_bytes_hash

#endif /* SPY_BYTES_H */
