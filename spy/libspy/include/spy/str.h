#ifndef SPY_STR_H
#define SPY_STR_H

#include "spy.h"
#include "spy/complex.h"
#include "spy/unsafe.h"
#include <stddef.h>

/* === String layout ===

   spy_StrObject contains length, hash and a ptr to utf8 data.

   spy_str_alloc allocates spy_StrObject AND the data buffer in a single
   allocation. So the memory layout for "foo" is more or less this (assuming 32 bit
   WASM):

   ADDR     3          length
   ADDR+4   ...        hash
   ADDR+8   ADDR+12    utf8
   ADDR+12  'f'
   ADDR+13  'o'
   ADDR+14  'o'

   Note that "co-allocation" is just an optimization, not a requirement.
*/

typedef struct {
    size_t length;
    int32_t hash;
    spy_gc_ptr_u8 utf8;
} spy_StrObject;

// Convenience macros for accessing the utf8 buffer.
#define spy_StrObject_UTF8(s) ((s)->utf8.p)
#define spy_StrObject_CHARS(s) ((const char *)spy_StrObject_UTF8(s))

/* SPY_STR_LITERAL(N, "content") is a struct initializer for spy_StrObject,
   useful for static globals and for-test literals. There are two versions
   depending on whether spy_gc_ptr_u8 carries a length (SPY_DEBUG). */
#ifdef SPY_DEBUG
#  define SPY_STR_LITERAL(N, S)                                                        \
      {                                                                                \
          (N), 0, {                                                                    \
              (uint8_t *)(S), (ptrdiff_t)(N)                                           \
          }                                                                            \
      }
#else
#  define SPY_STR_LITERAL(N, S)                                                        \
      {                                                                                \
          (N), 0, {                                                                    \
              (uint8_t *)(S)                                                           \
          }                                                                            \
      }
#endif

// Layout info exported for str.py.
typedef struct {
    size_t size;
    size_t length_offset;
    size_t hash_offset;
    size_t utf8_offset;
} _spy_StrObject_Layout;

_spy_StrObject_Layout WASM_EXPORT(_spy_StrObject_layout)(void);

spy_StrObject *WASM_EXPORT(spy_str_alloc)(size_t length);

spy_StrObject *WASM_EXPORT(spy_str_add)(spy_StrObject *a, spy_StrObject *b);

spy_StrObject *WASM_EXPORT(spy_str_replace)(
    spy_StrObject *original,
    spy_StrObject *old,
    spy_StrObject *new_str
);

spy_StrObject *WASM_EXPORT(spy_str_mul)(spy_StrObject *a, int32_t b);

bool WASM_EXPORT(spy_str_eq)(spy_StrObject *a, spy_StrObject *b);

static inline bool
spy_str_ne(spy_StrObject *a, spy_StrObject *b) {
    return !spy_str_eq(a, b);
}

// XXX: should we introduce a separate type Char?
spy_StrObject *WASM_EXPORT(spy_str_getitem)(spy_StrObject *s, int32_t i);

int32_t WASM_EXPORT(spy_str_len)(spy_StrObject *s);

spy_StrObject *WASM_EXPORT(spy_str_repr)(spy_StrObject *s);

int32_t WASM_EXPORT(spy_str_hash)(spy_StrObject *s);

#define spy_operator$str_add spy_str_add
#define spy_operator$str_mul spy_str_mul
#define spy_operator$str_eq spy_str_eq
#define spy_operator$str_ne spy_str_ne
#define spy_operator$str_to_complex128 spy_str_to_complex128
#define spy_builtins$str$replace spy_str_replace
#define spy_builtins$str$__getitem__ spy_str_getitem
#define spy_builtins$str$__len__ spy_str_len
#define spy_builtins$str$__str__ spy_str_identity
#define spy_builtins$str$__repr__ spy_str_repr

static inline spy_StrObject *
spy_str_identity(spy_StrObject *s) {
    return s;
}
#define spy_builtins$hash_str spy_str_hash

// __str__ methods of common builtin types
spy_StrObject *spy_builtins$i32$__str__(int32_t x);

spy_StrObject *spy_builtins$i8$__str__(int8_t x);

spy_StrObject *spy_builtins$u8$__str__(uint8_t x);

spy_StrObject *spy_builtins$f64$__str__(double x);

spy_StrObject *spy_builtins$bool$__str__(bool x);

// str -> numeric conversion operators
int32_t spy_operator$str_to_i32(spy_StrObject *s);

uint32_t spy_operator$str_to_u32(spy_StrObject *s);

int8_t spy_operator$str_to_i8(spy_StrObject *s);

uint8_t spy_operator$str_to_u8(spy_StrObject *s);

spy_Complex128 WASM_EXPORT(spy_str_to_complex128)(spy_StrObject *s);

#endif /* SPY_STR_H */
