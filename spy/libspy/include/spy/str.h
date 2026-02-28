#ifndef SPY_STR_H
#define SPY_STR_H

#include "spy.h"
#include <stddef.h>

typedef struct {
    size_t length;
    int32_t hash;
    const char utf8[];
} spy_Str;

spy_Str *WASM_EXPORT(spy_str_alloc)(size_t length);

spy_Str *WASM_EXPORT(spy_str_add)(spy_Str *a, spy_Str *b);

spy_Str *WASM_EXPORT(spy_str_mul)(spy_Str *a, int32_t b);

bool WASM_EXPORT(spy_str_eq)(spy_Str *a, spy_Str *b);

static inline bool
spy_str_ne(spy_Str *a, spy_Str *b) {
    return !spy_str_eq(a, b);
}

// XXX: should we introduce a separate type Char?
spy_Str *WASM_EXPORT(spy_str_getitem)(spy_Str *s, int32_t i);

int32_t WASM_EXPORT(spy_str_len)(spy_Str *s);

int32_t WASM_EXPORT(spy_str_hash)(spy_Str *s);

#define spy_operator$str_add spy_str_add
#define spy_operator$str_mul spy_str_mul
#define spy_operator$str_eq spy_str_eq
#define spy_operator$str_ne spy_str_ne
#define spy_builtins$str$__getitem__ spy_str_getitem
#define spy_builtins$str$__len__ spy_str_len
#define spy_builtins$hash_str spy_str_hash

// __str__ methods of common builtin types
spy_Str *spy_builtins$i32$__str__(int32_t x);

spy_Str *spy_builtins$i8$__str__(int8_t x);

spy_Str *spy_builtins$u8$__str__(uint8_t x);

spy_Str *spy_builtins$f64$__str__(double x);

spy_Str *spy_builtins$bool$__str__(bool x);

// str -> int conversion operators
int32_t spy_operator$str_to_i32(spy_Str *s);

uint32_t spy_operator$str_to_u32(spy_Str *s);

int8_t spy_operator$str_to_i8(spy_Str *s);

uint8_t spy_operator$str_to_u8(spy_Str *s);

// StringBuilder for f-string lowering
typedef struct {
    size_t length;   // bytes currently written
    size_t capacity; // allocated capacity of buf
    char *buf;       // mutable data buffer
} spy_StringBuilder;

spy_StringBuilder *WASM_EXPORT(spy_str_builder_new)(int32_t initial_capacity);
spy_StringBuilder *WASM_EXPORT(spy_str_builder_push)(spy_StringBuilder *sb, spy_Str *s);
spy_Str *WASM_EXPORT(spy_str_builder_build)(spy_StringBuilder *sb);

#define spy_builtins$str_builder_new spy_str_builder_new
#define spy_builtins$StringBuilder$push spy_str_builder_push
#define spy_builtins$StringBuilder$build spy_str_builder_build

// str.__str__ identity: needed so str(s) works when s: str
static inline spy_Str *
spy_str_identity(spy_Str *s) {
    return s;
}
#define spy_builtins$str$__str__ spy_str_identity

#endif /* SPY_STR_H */
