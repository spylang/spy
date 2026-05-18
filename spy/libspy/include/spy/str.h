#ifndef SPY_STR_H
#define SPY_STR_H

#include "spy.h"
#include "spy/complex.h"
#include <stddef.h>

/* === String layout ===

   spy_Str contains length, hash and a ptr to utf8 data.

   spy_Str_alloc allocates spy_Str AND the data buffer in a single allocation. So the
   memory layout for "foo" is more or less this (assuming 32 bit WASM):

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
    const uint8_t *utf8;
} spy_Str;

// Convenience macro to get (const char*)utf8
#define spy_Str_CHARS(s) ((const char *)(s)->utf8)

// Layout info exported for str.py.
typedef struct {
    size_t size;
    size_t length_offset;
    size_t hash_offset;
    size_t utf8_offset;
} _spy_Str_Layout;

_spy_Str_Layout WASM_EXPORT(_spy_Str_layout)(void);

spy_Str *WASM_EXPORT(spy_str_alloc)(size_t length);

spy_Str *WASM_EXPORT(spy_str_add)(spy_Str *a, spy_Str *b);

spy_Str
    *WASM_EXPORT(spy_str_replace)(spy_Str *original, spy_Str *old, spy_Str *new_str);

spy_Str *WASM_EXPORT(spy_str_mul)(spy_Str *a, int32_t b);

bool WASM_EXPORT(spy_str_eq)(spy_Str *a, spy_Str *b);

static inline bool
spy_str_ne(spy_Str *a, spy_Str *b) {
    return !spy_str_eq(a, b);
}

// XXX: should we introduce a separate type Char?
spy_Str *WASM_EXPORT(spy_str_getitem)(spy_Str *s, int32_t i);

int32_t WASM_EXPORT(spy_str_len)(spy_Str *s);

spy_Str *WASM_EXPORT(spy_str_repr)(spy_Str *s);

int32_t WASM_EXPORT(spy_str_hash)(spy_Str *s);

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

static inline spy_Str *
spy_str_identity(spy_Str *s) {
    return s;
}
#define spy_builtins$hash_str spy_str_hash

// __str__ methods of common builtin types
spy_Str *spy_builtins$i32$__str__(int32_t x);

spy_Str *spy_builtins$i8$__str__(int8_t x);

spy_Str *spy_builtins$u8$__str__(uint8_t x);

spy_Str *spy_builtins$f64$__str__(double x);

spy_Str *spy_builtins$bool$__str__(bool x);

// str -> numeric conversion operators
int32_t spy_operator$str_to_i32(spy_Str *s);

uint32_t spy_operator$str_to_u32(spy_Str *s);

int8_t spy_operator$str_to_i8(spy_Str *s);

uint8_t spy_operator$str_to_u8(spy_Str *s);

spy_Complex128 WASM_EXPORT(spy_str_to_complex128)(spy_Str *s);

#endif /* SPY_STR_H */
